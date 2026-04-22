let tg = window.Telegram.WebApp;
tg.expand();
tg.ready();
document.getElementById("dateInput").valueAsDate = new Date();

// --- ЛОГИКА ПЕРЕВОДОВ ---
const TRANSLATIONS = {
  RUS: {
    tab_shift: "💼 Смена", tab_reports: "📊 Отчеты", tab_settings: "⚙️ Настройки",
    t_work_data: "Данные о работе", l_date: "📅 Дата", l_status: "📌 Статус",
    opt_work: "💼 Работа", opt_l4: "💊 Больничный (L4)", opt_urlop: "🌴 Отпуск",
    l_end_date: "🏁 По (включительно)", l_object: "📍 Объект / Город", 
    l_abroad: "🌍 Заграница (EUR)", l_diet: "🥪 Командировка (Диета)",
    t_logistics: "Логистика и Часы", l_car: "🚛 Авто", l_route: "🛣 Маршрут",
    l_hours: "⏱ На объекте (ч)", l_drive: "🚗 За рулем (ч)", btn_send_shift: "Отправить отчет",
    t_progress: "🎯 Прогресс за месяц", t_audit: "📊 Интерактивный аудит ЗП",
    l_month_audit: "📅 Месяц", l_card: "💰 Пришло на карту", btn_audit: "Посчитать конверт",
    t_history: "📜 История и редактирование", l_month_history: "Выбери месяц", btn_history: "Показать смены",
    t_export: "📥 Экспорт Excel", l_month_export: "Выбери месяц", btn_export: "Прислать Excel в чат",
    t_lang: "Язык интерфейса", l_lang_select: "🌐 Язык", t_goal: "🎯 Моя финансовая цель", l_goal_name: "Название",
    l_goal_sum: "Сумма (zł)", t_profile: "Финансовый профиль (Ставки)", btn_save_settings: "Сохранить изменения",
    alert_hours: "⚠️ Укажи часы работы ИЛИ за рулем!", alert_audit: "⚠️ Выбери месяц и введи сумму!", alert_history: "⚠️ Выбери месяц для просмотра истории!",
    mot_start: "Начало положено! 🚀 Запиши пару смен.", mot_good: "Отличный старт! Двигаемся дальше. 💼", mot_fast: "Хороший темп! Копилка пополняется. 🔥", mot_close: "Уже близко! Поднажми! 💪", mot_done: "ЦЕЛЬ ДОСТИГНУТА! 🎉 Ты супер-профи!",
    default_goal: "Моя цель", objectInput: "Любой текст", routeInput: "Откуда - Куда", cardAmount: "Сумма в zł", goalNameInput: "Дом у моря", goalMotivation: "Загружаем данные..."
  },
  UKR: {
    tab_shift: "💼 Зміна", tab_reports: "📊 Звіти", tab_settings: "⚙️ Налаштування",
    t_work_data: "Дані про роботу", l_date: "📅 Дата", l_status: "📌 Статус",
    opt_work: "💼 Робота", opt_l4: "💊 Лікарняний (L4)", opt_urlop: "🌴 Відпустка",
    l_end_date: "🏁 По (включно)", l_object: "📍 Об'єкт / Місто", 
    l_abroad: "🌍 Закордон (EUR)", l_diet: "🥪 Відрядження (Дієта)",
    t_logistics: "Логістика та Години", l_car: "🚛 Авто", l_route: "🛣 Маршрут",
    l_hours: "⏱ На об'єкті (год)", l_drive: "🚗 За кермом (год)", btn_send_shift: "Відправити звіт",
    t_progress: "🎯 Прогрес за місяць", t_audit: "📊 Інтерактивний аудит ЗП",
    l_month_audit: "📅 Місяць", l_card: "💰 Прийшло на карту", btn_audit: "Порахувати конверт",
    t_history: "📜 Історія та редагування", l_month_history: "Обери місяць", btn_history: "Показати зміни",
    t_export: "📥 Експорт Excel", l_month_export: "Обери місяць", btn_export: "Надіслати Excel у чат",
    t_lang: "Мова інтерфейсу", l_lang_select: "🌐 Мова", t_goal: "🎯 Моя фінансова ціль", l_goal_name: "Назва",
    l_goal_sum: "Сума (zł)", t_profile: "Фінансовий профіль (Ставки)", btn_save_settings: "Зберегти зміни",
    alert_hours: "⚠️ Вкажи години роботи АБО за кермом!", alert_audit: "⚠️ Обери місяць та введи суму!", alert_history: "⚠️ Обери місяць для перегляду історії!",
    mot_start: "Початок покладено! 🚀 Запиши пару змін.", mot_good: "Гарний старт! Рухаємось далі. 💼", mot_fast: "Хороший темп! Скарбничка поповнюється. 🔥", mot_close: "Вже близько! Піднажми! 💪", mot_done: "ЦІЛЬ ДОСЯГНУТА! 🎉 Ти супер-профі!",
    default_goal: "Моя ціль", objectInput: "Будь-який текст", routeInput: "Звідки - Куди", cardAmount: "Сума в zł", goalNameInput: "Будинок біля моря", goalMotivation: "Завантажуємо дані..."
  },
  PL: {
    tab_shift: "💼 Zmiana", tab_reports: "📊 Raporty", tab_settings: "⚙️ Ustawienia",
    t_work_data: "Dane o pracy", l_date: "📅 Data", l_status: "📌 Status",
    opt_work: "💼 Praca", opt_l4: "💊 Zwolnienie (L4)", opt_urlop: "🌴 Urlop",
    l_end_date: "🏁 Do (włącznie)", l_object: "📍 Obiekt / Miasto", 
    l_abroad: "🌍 Zagranica (EUR)", l_diet: "🥪 Delegacja (Dieta)",
    t_logistics: "Logistyka i Godziny", l_car: "🚛 Auto", l_route: "🛣 Trasa",
    l_hours: "⏱ Na obiekcie (h)", l_drive: "🚗 Za kierownicą (h)", btn_send_shift: "Wyślij raport",
    t_progress: "🎯 Postęp w miesiącu", t_audit: "📊 Interaktywny audyt wypłaty",
    l_month_audit: "📅 Miesiąc", l_card: "💰 Wpłynęło na konto", btn_audit: "Oblicz kopertę",
    t_history: "📜 Historia i edycja", l_month_history: "Wybierz miesiąc", btn_history: "Pokaż zmiany",
    t_export: "📥 Eksport Excel", l_month_export: "Wybierz miesiąc", btn_export: "Wyślij Excel na czat",
    t_lang: "Język interfejsu", l_lang_select: "🌐 Język", t_goal: "🎯 Mój cel finansowy", l_goal_name: "Nazwa",
    l_goal_sum: "Kwota (zł)", t_profile: "Profil finansowy (Stawki)", btn_save_settings: "Zapisz zmiany",
    alert_hours: "⚠️ Podaj godziny pracy LUB za kierownicą!", alert_audit: "⚠️ Wybierz miesiąc i wpisz kwotę!", alert_history: "⚠️ Wybierz miesiąc, aby wyświetlić historię!",
    mot_start: "Początek zrobiony! 🚀 Zapisz parę zmian.", mot_good: "Świetny start! Idziemy dalej. 💼", mot_fast: "Dobre tempo! Skarbonka rośnie. 🔥", mot_close: "Już blisko! Dajesz! 💪", mot_done: "CEL OSIĄGNIĘTY! 🎉 Jesteś super-pro!",
    default_goal: "Mój cel", objectInput: "Dowolny tekst", routeInput: "Skąd - Dokąd", cardAmount: "Kwota w zł", goalNameInput: "Dom nad morzem", goalMotivation: "Wczytywanie danych..."
  }
};

let currentLang = "RUS";
let percent = 0; 

function applyLanguage(lang) {
  currentLang = lang;
  const t = TRANSLATIONS[lang];
  if (!t) return;

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
  if (!customGoalName) {
      document.getElementById("goalNameDisplay").innerText = t.default_goal;
  } else {
      document.getElementById("goalNameDisplay").innerText = customGoalName;
  }

  updateMotivationText();
}

function changeLanguage() {
    const selectedLang = document.getElementById("langInput").value;
    applyLanguage(selectedLang);
}

function updateMotivationText() {
    let motText = TRANSLATIONS[currentLang].mot_start;
    if (percent > 0) motText = TRANSLATIONS[currentLang].mot_good;
    if (percent > 30) motText = TRANSLATIONS[currentLang].mot_fast;
    if (percent > 70) motText = TRANSLATIONS[currentLang].mot_close;
    if (percent >= 100) motText = TRANSLATIONS[currentLang].mot_done;
    let motEl = document.getElementById("goalMotivation");
    if (motEl) motEl.innerText = motText;
}

// --- ЧТЕНИЕ ДАННЫХ ИЗ БОТА ---
const urlParams = new URLSearchParams(window.location.search);

let gTarget = parseFloat(urlParams.get("g_target")) || 8000;
let cNet = parseFloat(urlParams.get("c_net")) || 0;

if (gTarget > 0 && cNet > 0) {
    percent = Math.min((cNet / gTarget) * 100, 100);
} else {
    percent = 0;
}

if (urlParams.has("lang")) applyLanguage(urlParams.get("lang"));
else applyLanguage("RUS"); 

if (urlParams.has("base")) document.getElementById("baseRateInput").value = urlParams.get("base");
if (urlParams.has("extra")) document.getElementById("extraRateInput").value = urlParams.get("extra");
if (urlParams.has("eur")) document.getElementById("eurRateInput").value = urlParams.get("eur");
if (urlParams.has("drive")) document.getElementById("driveRateInput").value = urlParams.get("drive");
if (urlParams.has("drive_eur")) document.getElementById("driveEurRateInput").value = urlParams.get("drive_eur");
if (urlParams.has("car") && urlParams.get("car") !== "") document.getElementById("carInput").value = urlParams.get("car");

let passedGName = urlParams.get("g_name");
if (passedGName && passedGName !== "Моя цель" && passedGName !== "Финансовая цель" && passedGName !== "null") {
    document.getElementById("goalNameInput").value = passedGName;
    document.getElementById("goalNameDisplay").innerText = passedGName;
} else {
    document.getElementById("goalNameInput").value = "";
}

if (urlParams.has("g_target")) document.getElementById("goalTargetInput").value = urlParams.get("g_target");
document.getElementById("goalTextDisplay").innerText = `${cNet.toFixed(0)} / ${gTarget} zł`;

setTimeout(() => {
    document.getElementById("goalProgressBar").style.width = percent + "%";
}, 300);

document.getElementById("statusInput").addEventListener("change", function () {
    if (this.value === "L4" || this.value === "Urlop") {
      document.getElementById("endDateRow").style.display = "flex";
    } else {
      document.getElementById("endDateRow").style.display = "none";
      document.getElementById("endDateInput").value = "";
    }
});

function openTab(tabId) {
  document.querySelectorAll(".content").forEach((c) => c.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.getElementById("tab_" + tabId).classList.add("active");
}

function sendShift() {
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

  // --- ИСПРАВЛЕНИЕ: ЛОГИКА ДЛЯ ВОЖДЕНИЯ ---
  let h = parseFloat(data.hours) || 0;
  let d = parseFloat(data.drive) || 0;
  let hasRoute = data.route && data.route.includes("-");
  
  if (data.status === "Work" && h <= 0 && d <= 0 && !hasRoute) {
    return tg.showAlert(TRANSLATIONS[currentLang].alert_hours);
  }
  // ----------------------------------------------

  let flash = document.createElement('div');
  flash.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:white; z-index:9999; pointer-events:none; opacity:0.9; transition: opacity 0.15s ease-out;';
  document.body.appendChild(flash);

  let bolt = document.createElement('div');
  bolt.innerHTML = '⚡';
  bolt.style.cssText = 'position:fixed; top:50%; left:50%; transform:translate(-50%, -50%) scale(0.1); font-size:140px; z-index:10000; pointer-events:none; transition: transform 0.1s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.2s;';
  document.body.appendChild(bolt);

  requestAnimationFrame(() => {
      bolt.style.transform = 'translate(-50%, -50%) scale(1.2)';
      flash.style.opacity = '0';
  });

  if (tg.HapticFeedback) {
      tg.HapticFeedback.impactOccurred('heavy');
      setTimeout(() => tg.HapticFeedback.impactOccurred('rigid'), 100); 
  }

  setTimeout(() => {
      bolt.style.opacity = '0';
      tg.sendData(JSON.stringify(data));
      setTimeout(() => { flash.remove(); bolt.remove(); tg.close(); }, 150);
  }, 500);
}

function sendReportReq() {
  let monthVal = document.getElementById("reportMonth").value;
  let formattedMonth = monthVal ? monthVal.split("-")[1] + "." + monthVal.split("-")[0] : "";
  tg.sendData(JSON.stringify({ action: "get_report", month: formattedMonth }));
  tg.close();
}

function sendAuditReq() {
  let monthVal = document.getElementById("auditMonth").value;
  let formattedMonth = monthVal ? monthVal.split("-")[1] + "." + monthVal.split("-")[0] : "";
  let cardAmount = document.getElementById("cardAmount").value.replace(',', '.');
  if (!formattedMonth || !cardAmount) {
    return tg.showAlert(TRANSLATIONS[currentLang].alert_audit);
  }
  tg.sendData(JSON.stringify({ action: "audit", month: formattedMonth, card: cardAmount }));
  tg.close();
}

function sendSettings() {
  let data = {
    action: "update_settings",
    base_rate: document.getElementById("baseRateInput").value.replace(',', '.'),
    extra_rate: document.getElementById("extraRateInput").value.replace(',', '.'),
    rate_eur: document.getElementById("eurRateInput").value.replace(',', '.'),
    rate_drive: document.getElementById("driveRateInput").value.replace(',', '.'),
    rate_drive_eur: document.getElementById("driveEurRateInput").value.replace(',', '.'),
    goal_name: document.getElementById("goalNameInput").value,
    goal_target: document.getElementById("goalTargetInput").value.replace(',', '.'),
    lang: document.getElementById("langInput").value
  };
  tg.sendData(JSON.stringify(data));
  tg.close();
}

function sendHistoryReq() {
  let monthVal = document.getElementById("historyMonth").value;
  let formattedMonth = monthVal ? monthVal.split("-")[1] + "." + monthVal.split("-")[0] : "";
  if (!formattedMonth) {
    return tg.showAlert(TRANSLATIONS[currentLang].alert_history);
  }
  tg.sendData(JSON.stringify({ action: "history", month: formattedMonth }));
  tg.close();
}