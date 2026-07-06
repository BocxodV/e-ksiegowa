from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import AgentState
from app.skills.parser import parse_shift_text
from app.skills.guardrails import validate_shift_data
from app.tools.db_tool import save_shift_to_db

# Nodes Wrapper Functions

async def node_parse(state: AgentState) -> dict:
    """
    Calls parse_shift_text with raw_input and returns the parsed data.
    """
    result = await parse_shift_text(state["raw_input"])
    return {"parsed_data": result}

def node_validate(state: AgentState) -> dict:
    """
    Calls validate_shift_data with parsed_data and returns validation errors.
    """
    parsed = state.get("parsed_data") or {}
    errors = validate_shift_data(parsed)
    return {"validation_errors": errors}

def node_human_review(state: AgentState):
    """
    Placeholder node for Human-in-the-Loop review.
    Graph execution will be interrupted before reaching this node if compiled with interrupt_before.
    """
    pass

def node_ask_human(state: AgentState) -> dict:
    """
    If there are validation errors, formats a clarification question to ask the user.
    """
    errors = state.get("validation_errors", [])
    if not errors:
        return {"clarification_question": None}
    
    question = "⚠️ **Уточните данные смены:**\n" + "\n".join(f"• {e}" for e in errors)
    return {"clarification_question": question}

# Router (Conditional Edge)

def route_after_validation(state: AgentState) -> str:
    """
    Routes the execution path based on validation results:
    - If errors are present, routes to ask_human to pause and ask for input.
    - If no errors, routes to human_review.
    """
    errors = state.get("validation_errors", [])
    if errors:
        return "ask_human"
    return "human_review"

# Graph Assembly

builder = StateGraph(AgentState)

# Add Nodes
builder.add_node("parser", node_parse)
builder.add_node("validator", node_validate)
builder.add_node("ask_human", node_ask_human)
builder.add_node("human_review", node_human_review)
builder.add_node("saver", save_shift_to_db)

# Add Edges
builder.add_edge(START, "parser")
builder.add_edge("parser", "validator")

# Add Conditional Edges from validator
builder.add_conditional_edges(
    "validator",
    route_after_validation,
    {
        "ask_human": "ask_human",
        "human_review": "human_review"
    }
)

# If asking human, we halt execution here (or in human_review). We'll set interrupt_before on ask_human too.
builder.add_edge("ask_human", END)

# After human review, we proceed to saving in DB, then END
builder.add_edge("human_review", "saver")
builder.add_edge("saver", END)

# Compile Graph with Interrupt before human_review and MemorySaver Checkpointer
app_graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["ask_human", "human_review"]
)
