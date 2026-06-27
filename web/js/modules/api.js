// js/modules/api.js
import { tg } from '../core/telegram.js';
import { state, TRANSLATIONS } from '../core/state.js';

export function sendShift() {
    let data = {
        action: "add_shift", 
        date: document.getElementById("dateInput").value, 
        end_date: document.getElementById("endDateInput").value,
        status: document.getElementById("statusInput").value, 
        hours: document.getElementById("hoursInput").value.replace(',', '.'),
        drive: document.getElementById("driveInput").value.replace(',', '.'), 
        location: document.getElementById("objectInput").value,
        car: document.getElementById("carInput").value, 
        route: document.getElementById("routeInput").value,
        is_abroad: document.getElementById("abroadInput").checked, 
        is_trip: document.getElementById("dietInput").checked,
    };
    if (data.status === "Work" && !(parseFloat(data.hours)>0) && !(parseFloat(data.drive)>0) && !(data.route && data.route.includes("-"))) {
        return tg.showAlert(TRANSLATIONS[state.currentLang].alert_hours || "Укажи часы!");
    }
    tg.sendData(JSON.stringify(data)); 
    tg.close();
}

export function sendReportReq() { 
    tg.sendData(JSON.stringify({ action: "get_report", month: document.getElementById("reportMonth").value.split("-").reverse().join(".") })); 
    tg.close(); 
}

export function sendBossReportReq() { 
    tg.sendData(JSON.stringify({ action: "get_boss_report", month: document.getElementById("reportMonth").value.split("-").reverse().join(".") })); 
    tg.close(); 
}

export function sendLogisticsReportReq() { 
    tg.sendData(JSON.stringify({ action: "get_pure_logistics_report", month: document.getElementById("reportMonth").value.split("-").reverse().join(".") })); 
    tg.close(); 
}

export function sendHistoryReq() { 
    tg.sendData(JSON.stringify({ action: "history_view", month: document.getElementById("historyMonth").value.split("-").reverse().join(".") })); 
    tg.close(); 
}

export function sendHistoryEditReq() { 
    const dateVal = document.getElementById("historyEditDate").value;
    if (!dateVal) {
        alert("Выберите день!");
        return;
    }
    const parts = dateVal.split("-");
    const dateStr = `${parts[2]}.${parts[1]}.${parts[0]}`;
    tg.sendData(JSON.stringify({ action: "history_edit", date: dateStr })); 
    tg.close(); 
}

export function sendAnalyticsReq() { 
    tg.sendData(JSON.stringify({ action: "analytics", month: document.getElementById("analyticsMonth").value.split("-").reverse().join(".") })); 
    tg.close(); 
}

export function sendVacationStatsReq() { 
    tg.sendData(JSON.stringify({ action: "vacation_stats" })); 
    tg.close(); 
}

export function sendSettings() {
    let data = { 
        action: "update_settings", 
        goal_name: document.getElementById("goalNameInput").value, 
        goal_deadline: document.getElementById("goalDeadlineInput").value, 
        lang: document.getElementById("langInput").value 
    };
    
    ["base", "extra", "eur", "drive", "drive_eur"].forEach(k => { 
        let inputId = k.replace("_eur","Eur").replace("_rate","Rate") + "RateInput";
        let el = document.getElementById(inputId);
        if(el) data[k+"_rate"] = el.value.replace(',', '.'); 
    });
    data.goal_target = document.getElementById("goalTargetInput").value.replace(',', '.');
    const vacationInput = document.getElementById("totalVacationDaysInput");
    if(vacationInput) data.total_vacation_days = vacationInput.value.replace(',', '.');
    
    tg.sendData(JSON.stringify(data)); 
    tg.close();
}

export function sendAuditReq() {
    let m = document.getElementById("auditMonth").value.split("-").reverse().join(".");
    let c = document.getElementById("cardAmount").value.replace(',', '.');
    if (!m || !c) return tg.showAlert(TRANSLATIONS[state.currentLang].alert_audit || "Ошибка");
    tg.sendData(JSON.stringify({ action: "audit", month: m, card: c })); 
    tg.close();
}

export function openGoogleMaps() {
    const from = document.getElementById("routeFrom").value.trim();
    const to = document.getElementById("routeTo").value.trim();
    if (!to) {
        tg.showAlert(TRANSLATIONS[state.currentLang].alert_route_to_required || "⚠️ Кася просит указать хотя бы точку назначения (Куда)!");
        return;
    }
    let mapsUrl = "https://www.google.com/maps/dir/?api=1";
    if (from) mapsUrl += `&origin=${encodeURIComponent(from)}`;
    mapsUrl += `&destination=${encodeURIComponent(to)}`;

    const mainRouteInput = document.getElementById("routeInput");
    if (mainRouteInput) mainRouteInput.value = from ? `${from} - ${to}` : to;

    tg.openLink(mapsUrl);
}

export function sendFeedback() {
    const el = document.getElementById("feedbackTextInput");
    const text = el ? el.value.trim() : "";
    if (!text) {
        return tg.showAlert(TRANSLATIONS[state.currentLang].alert_feedback_empty || "Введите текст отзыва!");
    }
    tg.sendData(JSON.stringify({ action: "feedback", text: text }));
    tg.close();
}