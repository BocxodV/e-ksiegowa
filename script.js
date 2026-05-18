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
    l_month_audit: "📅 Месяц", l_card: "💰 Пришло на карту", btn_audit: "Посчитать конверт",
    t_history: "📜 История и редактирование", l_month_history: "Выбери месяц", btn_history: "Показать смены",
    t_export: "📥 Экспорт Excel", l_month_export: "Выбери месяц", btn_export: "Прислать Excel в чат",
    t_lang: "Язык интерфейса", l_lang_select: "🌐 Язык", t_goal: "🎯 Моя финансовая цель", l_goal_name: "Название",
    l_goal_sum: "Сумма (zł)", t_profile: "Финансовый профиль (Ставки)", btn_save_settings: "Сохранить изменения",
    alert_hours: "⚠️ Укажи часы работы ИЛИ за рулем!", alert_audit: "⚠️ Выбери месяц и введи сумму!", alert_history: "⚠️ Выбери месяц для просмотра истории!",
    mot_start: "Начало положено! 🚀 Отложи первую сумму.", mot_good: "Отличный старт! Двигаемся дальше. 💼", mot_fast: "Хороший темп! Копилка пополняется. 🔥", mot_close: "Уже близко! Поднажми! 💪", mot_done: "ЦЕЛЬ ДОСТИГНУТА! 🎉 Ты супер-профи!",
    default_goal: "Моя цель", objectInput: "Любой текст", routeInput: "Откуда - Куда", cardAmount: "Сумма в zł", goalNameInput: "Дом у моря", goalMotivation: "Загружаем данные...",
    t_analytics: "📈 Топ объектов (Аналитика)", l_month_analytics: "Выбери месяц", btn_analytics: "Показать Топ объектов",
    l_goal_date: "К какому сроку?", l_env: "✉️ Конверт (zł/h)", l_rate_eur: "💶 Ставка (EUR/h)", l_drive_zl: "🚗 Руль (zł/h)", l_drive_eur: "🚙 Руль (EUR/h)",
    t_support: "☕ Поддержать проект", t_support_desc: "Бот экономит твое время на расчетах? Угости ИИ-бухгалтершу кофе!", placeholder_card: "Сумма в zł",
    t_garage: "Мой Гараж", t_garage_desc: "Здесь мы скоро реализуем ручное добавление, управление списком и кнопку распознавания авто по фото!",
    t_nav: "Навигация", t_nav_desc: "Скоро здесь появится интерактивная карта для построения маршрутов и переход в Google Maps."
  },
  UKR: {
    t_work_data: "Дані про роботу", l_date: "📅 Дата", l_status: "📌 Статус",
    opt_work: "💼 Робота", opt_l4: "💊 Лікарняний (L4)", opt_urlop: "🌴 Відпустка",
    l_end_date: "🏁 По (включно)", l_object: "📍 Об'єкт / Місто", 
    l_abroad: "🌍 Закордон (EUR)", l_diet: "🥪 Відрядження (Дієта)",
    t_logistics: "Логістика та Години", l_car: "🚛 Авто", l_route: "🛣 Маршрут",
    l_hours: "⏱ На об'єкті (год)", l_drive: "🚗 За кермом (год)", btn_send_shift: "Відправити звіт",
    t_progress: "🎯 Моя скарбничка", t_audit: "📊 Інтерактивний аудит ЗП",
    l_month_audit: "📅 Місяць", l_card: "💰 Прийшло на карту", btn_audit: "Порахувати конверт",
    t_history: "📜 Історія та редагування", l_month_history: "Обери місяць", btn_history: "Показати зміни",
    t_export: "📥 Експорт Excel", l_month_export: "Обери місяць", btn_export: "Надіслати Excel у чат",
    t_lang: "Мова інтерфейсу", l_lang_select: "🌐 Мова", t_goal: "🎯 Моя фінансова ціль", l_goal_name: "Назва",
    l_goal_sum: "Сума (zł)", t_profile: "Фінансовий профіль (Ставки)", btn_save_settings: "Зберегти зміни",
    alert_hours: "⚠️ Вкажи години роботи АБО за кермом!", alert_audit: "⚠️ Обери місяць та введи суму!", alert_history: "⚠️ Обери місяць для перегляду історії!",
    mot_start: "Початок покладено! 🚀 Відклади першу суму.", mot_good: "Гарний старт! Рухаємось далі. 💼", mot_fast: "Хороший темп! Скарбничка поповнюється. 🔥", mot_close: "Вже близько! Піднажми! 💪", mot_done: "ЦІЛЬ ДОСЯГНУТА! 🎉 Ти супер-профи!",
    default_goal: "Моя ціль", objectInput: "Будь-який текст", routeInput: "Звідки - Куди", cardAmount: "Сума в zł", goalNameInput: "Будинок біля моря", goalMotivation: "Завантажуємо дані...",
    t_analytics: "📈 Топ об'єктів (Аналітика)", l_month_analytics: "Обери місяць", btn_analytics: "Показати Топ об'єктів",
    l_goal_date: "До якого терміну?", l_env: "✉️ Конверт (zł/h)", l_rate_eur: "💶 Ставка (EUR/h)", l_drive_zl: "🚗 Кермо (zł/h)", l_drive_eur: "🚙 Кермо (EUR/h)",
    t_support: "☕ Підтримати проєкт", t_support_desc: "Бот економить твій час на розрахунках? Пригости ШІ-бухгалтерку кавою!", placeholder_card: "Сума в zł",
    t_garage: "Мій Гараж", t_garage_desc: "Тут ми скоро реалізуємо ручне додавання, управління списком та кнопку розпізнавання авто за фото!",
    t_nav: "Навігація", t_nav_desc: "Скоро тут з'явиться інтерактивна карта для побудови маршрутів та перехід у Google Maps."
  },
  PL: {
    t_work_data: "Dane o pracy", l_date: "📅 Data", l_status: "📌 Status",
    opt_work: "💼 Praca", opt_l4: "💊 Zwolnienie (L4)", opt_urlop: "🌴 Urlop",
    l_end_date: "🏁 Do (włącznie)", l_object: "📍 Obiekt / Miasto", 
    l_abroad: "🌍 Zagranica (EUR)", l_diet: "🥪 Delegacja (Dieta)",
    t_logistics: "Logistyka i Godziny", l_car: "🚛 Auto", l_route: "🛣 Trasa",
    l_hours: "⏱ Na obiekcie (h)", l_drive: "🚗 Za kierownicą (h)", btn_send_shift: "Wyślij raport",
    t_progress: "🎯 Moja skarbonka", t_audit: "📊 Interaktywny audyt wypłaty",
    l_month_audit: "📅 Miesiąc", l_card: "💰 Wpłynęło na konto", btn_audit: "Oblicz kopertę",
    t_history: "📜 Historia i edycja", l_month_history: "Wybierz miesiąc", btn_history: "Pokaż zmiany",
    t_export: "📥 Eksport Excel", l_month_export: "Wybierz miesiąc", btn_export: "Wyślij Excel na czat",
    t_lang: "Język interfejsu", l_lang_select: "🌐 Język", t_goal: "🎯 Mój cel finansowy", l_goal_name: "Nazwa",
    l_goal_sum: "Kwota (zł)", t_profile: "Profil finansowy (Stawki)", btn_save_settings: "Zapisz zmiany",
    alert_hours: "⚠️ Podaj godziny pracy LUB za kierownicą!", alert_audit: "⚠️ Wybierz miesiąc i wpisz kwotę!", alert_history: "⚠️ Wybierz miesiąc, aby wyświetlić historię!",
    mot_start: "Początek zrobiony! 🚀 Odłóż pierwszą kwotę.", mot_good: "Świetny start! Idziemy dalej. 💼", mot_fast: "Dobre tempo! Skarbonka rośnie. 🔥", mot_close: "Już blisko! Dajesz! 💪", mot_done: "CEL OSIĄGNIĘTY! 🎉 Jesteś super-pro!",
    default_goal: "Mój cel", objectInput: "Dowolny tekst", routeInput: "Skąd - Dokąd", cardAmount: "Kwota w zł", goalNameInput: "Dom nad morzem", goalMotivation: "Wczytywanie danych...",
    t_analytics: "📈 Top obiektów (Analityka)", l_month_analytics: "Wybierz miesiąc", btn_analytics: "Pokaż Top obiektów",
    l_goal_date: "Do kiedy?", l_env: "✉️ Koperta (zł/h)", l_rate_eur: "💶 Stawka (EUR/h)", l_drive_zl: "🚗 Kółko (zł/h)", l_drive_eur: "🚙 Kółko (EUR/h)",
    t_support: "☕ Wesprzyj projekt", t_support_desc: "Bot oszczędza Twój czas? Postaw księgowej AI kawę!", placeholder_card: "Kwota w zł",
    t_garage: "Mój Garaż", t_garage_desc: "Wkrótce dodamy tu ręczne wprowadzanie, zarządzanie listą i przycisk rozpoznawania auta ze zdjęcia!",
    t_nav: "Nawigacja", t_nav_desc: "Wkrótce pojawi się tu interaktywna mapa do planowania tras i przejście do Google Maps."
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