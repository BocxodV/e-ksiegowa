// js/app.js
import { tg, initTelegram } from './core/telegram.js';
import { state, TRANSLATIONS } from './core/state.js';
import { openTab, setupSwipes, updatePolaroid } from './modules/tabs.js';
import { triggerCarScan } from './modules/camera.js';
import { sendShift, sendReportReq, sendBossReportReq, sendLogisticsReportReq, sendHistoryReq, sendHistoryEditReq, sendAnalyticsReq, sendVacationStatsReq, sendSettings, sendAuditReq, openGoogleMaps, sendFeedback } from './modules/api.js';

document.addEventListener('DOMContentLoaded', () => {
    initTelegram();
    setupSwipes();
    document.getElementById("dateInput").valueAsDate = new Date();

    // --- Localization & Financial Goal Logics ---
    function updateMotivationText() {
        let t = TRANSLATIONS[state.currentLang] || TRANSLATIONS["RUS"];
        let motText = t.mot_start || "Вперед!";
        if (state.percent > 0) motText = t.mot_good || "Отлично!";
        if (state.percent > 30) motText = t.mot_fast || "Быстро!";
        if (state.percent > 70) motText = t.mot_close || "Почти!";
        if (state.percent >= 100) motText = t.mot_done || "Готово!";
        let motEl = document.getElementById("goalMotivation");
        if (motEl) motEl.innerText = motText;
    }

    function applyLanguage(lang) {
        try {
            state.currentLang = lang;
            const t = TRANSLATIONS[lang] || TRANSLATIONS["RUS"];
            for (let key in t) {
                let el = document.getElementById(key);
                if (el) {
                    if ((el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && (el.type === 'text' || el.type === 'number' || el.tagName === 'TEXTAREA')) {
                        el.placeholder = t[key];
                    } else if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') {
                        if (key === "btn_send_shift" && urlParams.get("edit") === "true") {
                            el.innerText = t.btn_save_shift || t.btn_send_shift;
                        } else {
                            el.innerText = t[key];
                        }
                    }
                }
            }
            // Dynamic translation of help-link elements
            document.querySelectorAll('[id^="l_how_it_works_"]').forEach(el => {
                el.innerText = t.l_how_it_works || "Как это работает?";
            });
            document.getElementById("langInput").value = lang;
            let goalInput = document.getElementById("goalNameInput");
            let customGoalName = goalInput ? goalInput.value : "";
            let goalDisplay = document.getElementById("goalNameDisplay");
            if (goalDisplay) {
                goalDisplay.innerText = !customGoalName ? (t.default_goal || "Моя цель") : customGoalName;
            }
            updateMotivationText();
        } catch (e) {
            console.error("Language switch error:", e);
        }
    }

    function changeLanguage() {
        let lang = document.getElementById("langInput").value;
        applyLanguage(lang);
    }

    // --- Parse parameters from URL query string ---
    const urlParams = new URLSearchParams(window.location.search);
    state.gTarget = parseFloat(urlParams.get("g_target")) || 8000;
    state.cSav = parseFloat(urlParams.get("c_sav")) || 0; 
    state.percent = (state.gTarget > 0 && state.cSav > 0) ? Math.min((state.cSav / state.gTarget) * 100, 100) : 0;

    applyLanguage(urlParams.get("lang") || "RUS"); 

    ["base", "extra", "eur", "drive", "drive_eur", "car", "g_target", "g_dead", "vacation"].forEach(key => {
        if (urlParams.has(key)) {
            let inputMap = {"base":"baseRateInput", "extra":"extraRateInput", "eur":"eurRateInput", "drive":"driveRateInput", "drive_eur":"driveEurRateInput", "car":"carInput", "g_target":"goalTargetInput", "g_dead":"goalDeadlineInput", "vacation": "totalVacationDaysInput"};
            if(document.getElementById(inputMap[key])) document.getElementById(inputMap[key]).value = urlParams.get(key);
        }
    });

    let passedGName = urlParams.get("g_name");
    if (passedGName && passedGName !== "Моя цель" && passedGName !== "null") {
        let gNameInput = document.getElementById("goalNameInput");
        if(gNameInput) gNameInput.value = passedGName;
        let gNameDisp = document.getElementById("goalNameDisplay");
        if(gNameDisp) gNameDisp.innerText = passedGName;
    }

    let goalTxtDisp = document.getElementById("goalTextDisplay");
    if(goalTxtDisp) goalTxtDisp.innerText = `${state.cSav.toFixed(0)} / ${state.gTarget} zł`;
    setTimeout(() => { 
        let pb = document.getElementById("goalProgressBar");
        if(pb) pb.style.width = state.percent + "%"; 
    }, 300);

    // --- Prepopulate form inputs for editing mode ---
    if (urlParams.get("edit") === "true") {
        const edate = urlParams.get("edate");
        const estatus = urlParams.get("estatus");
        const eobj = urlParams.get("eobj");
        const ehours = urlParams.get("ehours");
        const edrive = urlParams.get("edrive");
        const ecar = urlParams.get("ecar");
        const eroute = urlParams.get("eroute");
        const eabroad = urlParams.get("eabroad") === "1" || urlParams.get("eabroad") === "true";
        const ediet = urlParams.get("ediet") === "1" || urlParams.get("ediet") === "true";

        if (edate) document.getElementById("dateInput").value = edate;
        if (estatus) {
            const statusEl = document.getElementById("statusInput");
            statusEl.value = estatus;
            document.getElementById("endDateRow").style.display = (estatus === "L4" || estatus === "Urlop") ? "flex" : "none";
        }
        if (eobj) document.getElementById("objectInput").value = eobj;
        if (ehours) document.getElementById("hoursInput").value = ehours;
        if (edrive) document.getElementById("driveInput").value = edrive;
        if (ecar) {
            document.getElementById("carInput").value = ecar;
            document.getElementById("garageCarInput").value = ecar;
        }
        if (eroute) {
            document.getElementById("routeInput").value = eroute;
            if (eroute.includes(" - ")) {
                let parts = eroute.split(" - ");
                if (document.getElementById("routeFrom")) document.getElementById("routeFrom").value = parts[0] || "";
                if (document.getElementById("routeTo")) document.getElementById("routeTo").value = parts[1] || "";
            }
        }
        document.getElementById("abroadInput").checked = eabroad;
        document.getElementById("dietInput").checked = ediet;

        // Disable changing date when editing an existing shift
        document.getElementById("dateInput").disabled = true;

        // Change button text to indicate update mode
        const t = TRANSLATIONS[state.currentLang] || TRANSLATIONS["RUS"];
        const btn = document.getElementById("btn_send_shift");
        if (btn) {
            btn.innerText = t.btn_save_shift || "Сохранить изменения";
        }
    }

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
    populateDatalist('garageCarsList', urlParams.get('cars') || "");

    // --- Synchronize vehicles and date properties ---
    const mainCarInput = document.getElementById("carInput");
    const garageCarInput = document.getElementById("garageCarInput");
    if (mainCarInput && garageCarInput) {
        mainCarInput.addEventListener("input", (e) => { garageCarInput.value = e.target.value; });
        mainCarInput.addEventListener("change", (e) => { garageCarInput.value = e.target.value; });
        garageCarInput.addEventListener("input", (e) => { mainCarInput.value = e.target.value; });
        garageCarInput.addEventListener("change", (e) => { mainCarInput.value = e.target.value; });
    }

    document.getElementById("statusInput").addEventListener("change", function () {
        document.getElementById("endDateRow").style.display = (this.value === "L4" || this.value === "Urlop") ? "flex" : "none";
    });

    // --- Synchronize route and destinations ---
    const routeFrom = document.getElementById("routeFrom");
    const routeTo = document.getElementById("routeTo");
    const mainRouteInput = document.getElementById("routeInput");

    function syncRoute() {
        if (!mainRouteInput) return;
        const fromText = routeFrom ? routeFrom.value.trim() : "";
        const toText = routeTo ? routeTo.value.trim() : "";

        if (fromText && toText) {
            mainRouteInput.value = `${fromText} - ${toText}`;
        } else if (fromText) {
            mainRouteInput.value = fromText;
        } else if (toText) {
            mainRouteInput.value = toText;
        } else {
            mainRouteInput.value = "";
        }
    }

    if (routeFrom) routeFrom.addEventListener("input", syncRoute);
    if (routeTo) routeTo.addEventListener("input", syncRoute);

    // --- Bind handlers globally for HTML onclick listeners ---
    window.openTab = openTab;
    window.changeLanguage = changeLanguage;
    window.triggerCarScan = triggerCarScan;
    window.sendShift = sendShift;
    window.sendReportReq = sendReportReq;
    window.sendBossReportReq = sendBossReportReq;
    window.sendLogisticsReportReq = sendLogisticsReportReq;
    window.sendHistoryReq = sendHistoryReq;
    window.sendHistoryEditReq = sendHistoryEditReq;
    window.sendAnalyticsReq = sendAnalyticsReq;
    window.sendVacationStatsReq = sendVacationStatsReq;
    window.sendSettings = sendSettings;
    window.sendAuditReq = sendAuditReq;
    window.openGoogleMaps = openGoogleMaps;
    window.sendFeedback = sendFeedback;

    window.showHelp = function(sectionId) {
        const modal = document.getElementById("helpModal");
        const titleEl = document.getElementById("helpTitle");
        const textEl = document.getElementById("helpText");
        
        let t = TRANSLATIONS[state.currentLang] || TRANSLATIONS["RUS"];
        
        titleEl.innerText = t.help_title || "Справка";
        textEl.innerText = t["help_" + sectionId] || "";
        modal.style.display = "block";
    };

    window.closeHelp = function() {
        document.getElementById("helpModal").style.display = "none";
    };

    window.onclick = function(event) {
        const modal = document.getElementById("helpModal");
        if (event.target == modal) {
            modal.style.display = "none";
        }
    };

    // Open the default workspace tab
    openTab('shift');
});