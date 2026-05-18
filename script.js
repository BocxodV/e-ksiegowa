let tg = window.Telegram.WebApp;
tg.expand();
tg.ready();
document.getElementById("dateInput").valueAsDate = new Date();

// --- ЛОГИКА ПЕРЕВОДОВ ---
const TRANSLATIONS = {
  RUS: {
    t_work_data: "Данные о работе", l_date: "📅 Дата", l_status: "📌 Статус",
    opt_work: "💼 Работа", opt_l4: "💊 Больничный (L4)", opt_urlop: "🌴 Отпуск",
    l_end_date: "🏁 По (включительно)", l_object: "📍 Объект / Город", 
    l_abroad: "🌍 Заграница (EUR)", l_diet: "🥪 Командировка (Диета)",
    t_logistics: "Логистика и Часы", l_car: "🚛 Авто", l_route: "🛣 Маршрут",
    l_hours: "⏱ На объекте (ч)", l_drive: "🚗 За рулем (ч)", btn_send_shift: "Отправить отчет",
    t_progress: "🎯 Моя копилка", t_audit: "📊 Интерактивный аудит ЗП",
    l_month_audit: "📅 Месяц", l_card: "💰 На карту", btn_audit: "Посчитать конверт",
    t_history: "📜 История и редактирование", l_month_history: "Месяц", btn_history: "Показать смены",
    t_export: "📥 Экспорт Excel", l_month_export: "Месяц", btn_export: "Прислать Excel в чат",
    t_lang: "Язык интерфейса", l_lang_select: "🌐 Язык", t_goal: "🎯 Моя финансовая цель", l_goal_name: "Название",
    l_goal_sum: "Сумма (zł)", t_profile: "Финансовый профиль (Ставки)", btn_save_settings: "Сохранить настройки",
    alert_hours: "⚠️ Укажи часы работы ИЛИ за рулем!", alert_audit: "⚠️ Выбери месяц и введи сумму!", alert_history: "⚠️ Выбери месяц для просмотра истории!",
    mot_start: "Начало положено! 🚀", mot_good: "Отличный старт! 💼", mot_fast: "Хороший темп! 🔥", mot_close: "Уже близко! 💪", mot_done: "ЦЕЛЬ ДОСТИГНУТА! 🎉",
    default_goal: "Моя цель", objectInput: "Любой текст", routeInput: "Откуда - Куда", cardAmount: "Сумма в zł", goalNameInput: "Дом у моря", goalMotivation: "Загружаем данные...",
    t_analytics: "📈 Топ объектов", l_month_analytics: "Месяц", btn_analytics: "Показать Топ объектов",
    l_goal_date: "Срок?", l_env: "✉️ Конверт (zł/h)", l_rate_eur: "💶 Ставка (EUR/h)", l_drive_zl: "🚗 Руль (zł/h)", l_drive_eur: "🚙 Руль (EUR/h)",
    placeholder_card: "Сумма в zł"
  },
  // (Остальные языки можно дополнить по аналогии, сократив длинные фразы для аккуратности)
  UKR: {
    t_work_data: "Дані про роботу", btn_send_shift: "Відправити звіт", default_goal: "Моя ціль"
  },
  PL: {
    t_work_data: "Dane o pracy", btn_send_shift: "Wyślij raport", default_goal: "Mój cel"
  }
};

let currentLang = "RUS";
let percent = 0; 

function applyLanguage(lang) {
  currentLang = lang;
  const t = TRANSLATIONS[lang] || TRANSLATIONS["RUS"];
  for (let key in t) {
      let el = document.getElementById(key);
      if (el) {
          if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'number')) {
              el.placeholder = t[key];
          } else if (el.tagName !== 'INPUT') {
              el.innerText = t[key];
          }
      }
  }
  document.getElementById("langInput").value = lang;
  let customGoalName = document.getElementById("goalNameInput").value;
  document.getElementById("goalNameDisplay").innerText = !customGoalName ? t.default_goal : customGoalName;
  updateMotivationText();
}

function changeLanguage() {
    applyLanguage(document.getElementById("langInput").value);
}

function updateMotivationText() {
    let t = TRANSLATIONS[currentLang] || TRANSLATIONS["RUS"];
    let motText = t.mot_start;
    if (percent > 0) motText = t.mot_good;
    if (percent > 30) motText = t.mot_fast;
    if (percent > 70) motText = t.mot_close;
    if (percent >= 100) motText = t.mot_done;
    let motEl = document.getElementById("goalMotivation");
    if (motEl) motEl.innerText = motText;
}

// --- ЧТЕНИЕ ДАННЫХ ИЗ URL ---
const urlParams = new URLSearchParams(window.location.search);
let gTarget = parseFloat(urlParams.get("g_target")) || 8000;
let cSav = parseFloat(urlParams.get("c_sav")) || 0; 
percent = (gTarget > 0 && cSav > 0) ? Math.min((cSav / gTarget) * 100, 100) : 0;

applyLanguage(urlParams.get("lang") || "RUS"); 

["base", "extra", "eur", "drive", "drive_eur", "car", "g_target", "g_dead"].forEach(key => {
    if (urlParams.has(key)) {
        let inputMap = {"base":"baseRateInput", "extra":"extraRateInput", "eur":"eurRateInput", "drive":"driveRateInput", "drive_eur":"driveEurRateInput", "car":"carInput", "g_target":"goalTargetInput", "g_dead":"goalDeadlineInput"};
        if(document.getElementById(inputMap[key])) document.getElementById(inputMap[key]).value = urlParams.get(key);
    }
});

let passedGName = urlParams.get("g_name");
if (passedGName && passedGName !== "Моя цель" && passedGName !== "null") {
    document.getElementById("goalNameInput").value = passedGName;
    document.getElementById("goalNameDisplay").innerText = passedGName;
}

document.getElementById("goalTextDisplay").innerText = `${cSav.toFixed(0)} / ${gTarget} zł`;
setTimeout(() => { document.getElementById("goalProgressBar").style.width = percent + "%"; }, 300);

// --- НАПОЛНЕНИЕ СПИСКОВ ---
function populateDatalist(listId, dataString) {
    const list = document.getElementById(listId);
    if (!list || !dataString) return;
    decodeURIComponent(dataString).split(',').forEach(item => {
        if (item.trim() !== "") {
            const option = document.createElement('option');
            option.value = item;
            list.appendChild(option);
        }
    });
}
populateDatalist('locationsList', urlParams.get('locs') || "");
populateDatalist('carsList', urlParams.get('cars') || "");

document.getElementById("statusInput").addEventListener("change", function () {
    document.getElementById("endDateRow").style.display = (this.value === "L4" || this.value === "Urlop") ? "flex" : "none";
});

// --- НОВАЯ ЛОГИКА ПЕРЕКЛЮЧЕНИЯ ВКЛАДОК ---
const tabsOrder = ['shift', 'garage', 'route', 'envelope', 'delete', 'export', 'analytics', 'savings', 'settings'];

function openTab(tabId) {
  const allContents = document.querySelectorAll(".content");
  const allTabs = document.querySelectorAll(".v-tab"); 
  
  allContents.forEach(c => { c.classList.remove("active"); c.classList.remove("page-fade"); });
  allTabs.forEach(t => t.classList.remove("active"));
  
  const targetContent = document.getElementById(tabId);
  if (targetContent) {
      targetContent.classList.add("active");
      // Прокручиваем страницу наверх при смене вкладки
      document.querySelector('.planner-page').scrollTop = 0;
      setTimeout(() => { targetContent.classList.add("page-fade"); }, 10);
  }
  
  const targetTab = document.getElementById("tab_" + tabId);
  if (targetTab) targetTab.classList.add("active");

  if (window.Telegram.WebApp.HapticFeedback) window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
}

// --- ЛОГИКА СВАЙПОВ ПО СТРАНИЦЕ (Лево-Право) ---
let touchStartX = 0;
let touchEndX = 0;
document.querySelector('.planner-page').addEventListener('touchstart', e => { touchStartX = e.changedTouches[0].screenX; }, { passive: true });
document.querySelector('.planner-page').addEventListener('touchend', e => { touchEndX = e.changedTouches[0].screenX; handleSwipe(); });

function handleSwipe() {
    let swipeDistance = touchEndX - touchStartX;
    let threshold = 60; 
    let activeTabElement = document.querySelector('.content.active');
    if (!activeTabElement) return;
    
    let currentIndex = tabsOrder.indexOf(activeTabElement.id);
    if (swipeDistance < -threshold && currentIndex < tabsOrder.length - 1) openTab(tabsOrder[currentIndex + 1]);
    if (swipeDistance > threshold && currentIndex > 0) openTab(tabsOrder[currentIndex - 1]);
}

// --- ОТПРАВКА ДАННЫХ В БОТА ---
function sendShift() {
  let data = {
    action: "add_shift", date: document.getElementById("dateInput").value, end_date: document.getElementById("endDateInput").value,
    status: document.getElementById("statusInput").value, hours: document.getElementById("hoursInput").value.replace(',', '.'),
    drive: document.getElementById("driveInput").value.replace(',', '.'), location: document.getElementById("objectInput").value,
    car: document.getElementById("carInput").value, route: document.getElementById("routeInput").value,
    is_abroad: document.getElementById("abroadInput").checked, is_trip: document.getElementById("dietInput").checked,
  };
  if (data.status === "Work" && !(parseFloat(data.hours)>0) && !(parseFloat(data.drive)>0) && !(data.route && data.route.includes("-"))) {
    return tg.showAlert(TRANSLATIONS[currentLang].alert_hours || "Укажи часы!");
  }
  tg.sendData(JSON.stringify(data)); tg.close();
}

function sendReportReq() { tg.sendData(JSON.stringify({ action: "get_report", month: document.getElementById("reportMonth").value.split("-").reverse().join(".") })); tg.close(); }
function sendHistoryReq() { tg.sendData(JSON.stringify({ action: "history", month: document.getElementById("historyMonth").value.split("-").reverse().join(".") })); tg.close(); }
function sendAnalyticsReq() { tg.sendData(JSON.stringify({ action: "analytics", month: document.getElementById("analyticsMonth").value.split("-").reverse().join(".") })); tg.close(); }
function sendSettings() {
  let data = { action: "update_settings", goal_name: document.getElementById("goalNameInput").value, goal_deadline: document.getElementById("goalDeadlineInput").value, lang: document.getElementById("langInput").value };
  ["base", "extra", "eur", "drive", "drive_eur"].forEach(k => { data[k+"_rate"] = document.getElementById(k.replace("_eur","Eur").replace("_rate","Rate")+"RateInput")?.value.replace(',','.'); });
  data.goal_target = document.getElementById("goalTargetInput").value.replace(',', '.');
  tg.sendData(JSON.stringify(data)); tg.close();
}
function sendAuditReq() {
  let m = document.getElementById("auditMonth").value.split("-").reverse().join("."), c = document.getElementById("cardAmount").value.replace(',', '.');
  if (!m || !c) return tg.showAlert(TRANSLATIONS[currentLang].alert_audit || "Ошибка");
  tg.sendData(JSON.stringify({ action: "audit", month: m, card: c })); tg.close();
}