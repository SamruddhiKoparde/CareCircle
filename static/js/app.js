
"use strict";

/* =========================================================
   CARECIRCLE — FRONTEND APPLICATION
   Uses the existing FastAPI session-cookie authentication.
========================================================= */

const API = "/api";

const state = {
    user: null,
    dashboard: null,
    medications: [],
    doses: [],
    appointments: [],
    members: [],
    loginMode: "patient"
};

const $ = (selector) => document.querySelector(selector);

const escapeHTML = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);

function localDateString(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function formatDate(value) {
    if (!value) return "Not scheduled";

    return new Date(value).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}

function formatTime(value) {
    if (!value) return "";

    return new Date(value).toLocaleTimeString("en-IN", {
        hour: "numeric",
        minute: "2-digit"
    });
}

function formatDateTime(value) {
    if (!value) return "Not scheduled";

    return `${formatDate(value)} · ${formatTime(value)}`;
}

function showToast(message, type = "success") {
    const toast = $("#toast");

    toast.textContent = message;
    toast.className = `toast show ${type}`;

    clearTimeout(showToast.timeout);

    showToast.timeout = setTimeout(() => {
        toast.className = "toast";
    }, 3500);
}

function showModal(title, content) {
    $("#modalTitle").textContent = title;
    $("#modalContent").innerHTML = content;
    $("#modalBackdrop").classList.remove("hidden");
}

function closeModal() {
    $("#modalBackdrop").classList.add("hidden");
    $("#modalContent").innerHTML = "";
}

function showError(container, message) {
    container.innerHTML = `
        <div class="empty-state">
            ${escapeHTML(message)}
        </div>
    `;
}

async function api(path, options = {}) {
    const settings = {
        method: options.method || "GET",
        credentials: "same-origin",
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {})
        }
    };

    if (options.body) {
        settings.body = JSON.stringify(options.body);
    }

    const response = await fetch(`${API}${path}`, settings);

    let data = {};

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        const message =
            data.detail ||
            data.message ||
            `Request failed (${response.status})`;

        if (response.status === 401 && path !== "/auth/login" &&
            path !== "/auth/member-login") {
            showLogin();
        }

        throw new Error(message);
    }

    return data;
}

/* =========================================================
   AUTHENTICATION
========================================================= */

function setupLoginModes() {
    const form = $("#loginForm");

    const modeSelector = document.createElement("div");
    modeSelector.className = "login-mode-selector";
    modeSelector.innerHTML = `
        <button type="button" class="btn btn-secondary login-mode active"
                data-mode="patient">Patient</button>
        <button type="button" class="btn btn-secondary login-mode"
                data-mode="member">Family / Caretaker</button>
    `;

    const emailLabel = form.querySelector('label[for="loginEmail"]');

    form.insertBefore(modeSelector, emailLabel);

    const patientIdLabel = document.createElement("label");
    patientIdLabel.htmlFor = "loginPatientId";
    patientIdLabel.textContent = "Patient account ID";
    patientIdLabel.className = "member-login-field hidden";

    const patientIdInput = document.createElement("input");
    patientIdInput.id = "loginPatientId";
    patientIdInput.type = "number";
    patientIdInput.min = "1";
    patientIdInput.placeholder = "Enter the patient's account ID";
    patientIdInput.className = "member-login-field hidden";

    form.insertBefore(patientIdLabel, emailLabel);
    form.insertBefore(patientIdInput, emailLabel);

    modeSelector.addEventListener("click", (event) => {
        const button = event.target.closest("[data-mode]");
        if (!button) return;

        state.loginMode = button.dataset.mode;

        modeSelector.querySelectorAll("button").forEach((item) => {
            item.classList.toggle("active", item === button);
        });

        const isMember = state.loginMode === "member";

        patientIdLabel.classList.toggle("hidden", !isMember);
        patientIdInput.classList.toggle("hidden", !isMember);
        patientIdInput.required = isMember;
    });
}

async function handleLogin(event) {
    event.preventDefault();

    const email = $("#loginEmail").value.trim();
    const passcode = $("#loginPasscode").value;
    const error = $("#loginError");
    const button = $("#loginButton");

    error.textContent = "";
    button.disabled = true;
    button.textContent = "Signing in...";

    try {
        if (state.loginMode === "member") {
            const patientId = Number($("#loginPatientId").value);

            if (!Number.isInteger(patientId) || patientId <= 0) {
                throw new Error("Enter a valid patient account ID.");
            }

            await api("/auth/member-login", {
                method: "POST",
                body: {
                    email,
                    passcode,
                    patient_id: patientId
                }
            });
        } else {
            await api("/auth/login", {
                method: "POST",
                body: { email, passcode }
            });
        }

        await loadApplication();

    } catch (error) {
        error.textContent = error.message;
    } finally {
        button.disabled = false;
        button.innerHTML = 'Sign in <span aria-hidden="true">→</span>';
    }
}

function showLogin() {
    $("#authScreen").classList.remove("hidden");
    $("#appScreen").classList.add("hidden");

    state.user = null;
    state.dashboard = null;
}

async function logout() {
    try {
        await api("/auth/logout", { method: "POST" });
    } catch (error) {
        console.error("Logout error:", error);
    }

    showLogin();
    showToast("You have signed out.");
}

/* =========================================================
   APPLICATION INITIALIZATION
========================================================= */

async function loadApplication() {
    const response = await api("/auth/me");

    state.user = response.user;

    $("#authScreen").classList.add("hidden");
    $("#appScreen").classList.remove("hidden");

    $("#userName").textContent = state.user.name;
    $("#userRole").textContent =
        state.user.role === "patient"
            ? "Patient account"
            : state.user.role === "family"
                ? "Family member"
                : "Caretaker";

    $("#userAvatar").textContent =
        (state.user.name || "U").charAt(0).toUpperCase();

    // Care-team administration belongs to the patient account.
    if (state.user.role !== "patient") {
        document.querySelector('[data-page="care-team"]')
            ?.classList.add("hidden");

        $("#inviteMemberButton")?.classList.add("hidden");
    }

    navigate("overview");
    await refreshAll();
}

async function refreshAll() {
    await loadDashboard();
    await Promise.allSettled([
        loadMedications(),
        loadAppointments(),
        loadCareTeam()
    ]);
}

/* =========================================================
   NAVIGATION
========================================================= */

function navigate(page) {
    const target = $(`#page-${page}`);

    if (!target) return;

    if (page === "care-team" && state.user?.role !== "patient") {
        showToast("Only the patient can manage the care team.", "error");
        return;
    }

    document.querySelectorAll(".page").forEach((item) => {
        item.classList.remove("active");
    });

    target.classList.add("active");

    document.querySelectorAll(".nav-item").forEach((item) => {
        item.classList.toggle("active", item.dataset.page === page);
    });

    const pageNames = {
        overview: "Overview",
        medications: "Medications",
        appointments: "Appointments",
        "care-team": "Care team",
        activity: "Activity"
    };

    $("#breadcrumbPage").textContent = pageNames[page] || page;

    $("#sidebar").classList.remove("mobile-open");
}

/* =========================================================
   DASHBOARD
========================================================= */

async function loadDashboard() {
    const data = await api("/dashboard");

    state.dashboard = data;

    const metrics = data.metrics || {};

    $("#metricMedications").textContent =
        metrics.active_medications ?? 0;

    $("#metricDoses").textContent =
        metrics.doses_today ?? 0;

    const confirmed =
        (metrics.patient_confirmed || 0) +
        (metrics.caregiver_confirmed || 0);

    $("#metricConfirmed").textContent = confirmed;

    $("#metricAttention").textContent =
        (metrics.awaiting_confirmation || 0) +
        (metrics.missed || 0);

    const today = new Date();

    $("#todayDate").textContent =
        today.toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric"
        }).toUpperCase();

    const hour = today.getHours();

    const greeting =
        hour < 12 ? "Good morning" :
        hour < 17 ? "Good afternoon" :
        "Good evening";

    $("#greeting").textContent =
        `${greeting}, ${data.patient?.full_name || state.user.name}`;

    const total = metrics.doses_today || 0;
    const percentage = total
        ? Math.round((confirmed / total) * 100)
        : 0;

    $("#progressPercent").textContent = `${percentage}%`;

    $("#progressPatient").textContent =
        metrics.patient_confirmed || 0;

    $("#progressCaregiver").textContent =
        metrics.caregiver_confirmed || 0;

    $("#progressRemaining").textContent =
        Math.max(0, total - confirmed);

    $("#progressCircle").style.background =
        `conic-gradient(#258b72 ${percentage}%, #e8eeeb ${percentage}%)`;

    renderTodayMedications(data.today_doses || []);
    renderDashboardAppointments(data.upcoming_appointments || []);
    renderDashboardActivity(data.recent_activity || []);
}

/* =========================================================
   MEDICATIONS AND DOSES
========================================================= */

async function loadMedications() {
    const [medicationResult, doseResult] = await Promise.all([
        api("/medications"),
        api(`/medications/doses?target_date=${localDateString()}`)
    ]);

    state.medications = (medicationResult.medications || []).map((medication) => {
    let scheduleTimes = medication.schedule_times || [];

    if (typeof scheduleTimes === "string") {
        try {
            scheduleTimes = JSON.parse(scheduleTimes);
        } catch {
            scheduleTimes = [];
        }
    }

    return {
        ...medication,
        schedule_times: Array.isArray(scheduleTimes) ? scheduleTimes : []
    };
});
    state.doses = doseResult.doses || [];

    renderMedicationTable();
}

function statusLabel(status) {
    const labels = {
        upcoming: "Upcoming",
        awaiting_confirmation: "Awaiting confirmation",
        taken: "Patient confirmed",
        caregiver_confirmed: "Caregiver confirmed",
        missed: "Missed"
    };

    return labels[status] || status || "Unknown";
}

function statusClass(status) {
    return String(status || "unknown").replaceAll("_", "-");
}

function renderTodayMedications(doses) {
    const container = $("#todayMedicationList");

    if (!doses.length) {
        container.innerHTML = `
            <div class="empty-state">
                No medication doses scheduled for today.
            </div>
        `;
        return;
    }

    container.innerHTML = doses.map((dose) => {
        const canConfirm =
            ["upcoming", "awaiting_confirmation"].includes(dose.status);

        return `
            <div class="medication-row">
                <div class="medication-info">
                    <strong>${escapeHTML(dose.medication_name)}</strong>
                    <small>${escapeHTML(dose.dosage || "")}</small>
                    <small>${formatTime(dose.scheduled_for)}</small>
                    <span class="status-badge ${statusClass(dose.status)}">
                        ${escapeHTML(statusLabel(dose.status))}
                    </span>
                    ${
                        dose.confirmed_by_name
                            ? `<small>Reported by ${escapeHTML(dose.confirmed_by_name)}</small>`
                            : ""
                    }
                </div>

                ${
                    canConfirm
                        ? `<button class="btn btn-secondary dose-confirm-button"
                                   data-dose-id="${dose.id}">
                                Confirm
                           </button>`
                        : ""
                }
            </div>
        `;
    }).join("");
}

function renderMedicationTable() {
    const container = $("#medicationFullList");

    if (!state.medications.length) {
        container.innerHTML = `
            <div class="empty-state">
                No medications have been added yet.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Medication</th>
                    <th>Dosage</th>
                    <th>Schedule</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${state.medications.map((medication) => `
                    <tr>
                        <td>
                            <strong>${escapeHTML(medication.name)}</strong>
                            <br>
                            <small>${escapeHTML(medication.instructions || "")}</small>
                        </td>
                        <td>${escapeHTML(medication.dosage)}</td>
                        <td>${(medication.schedule_times || [])
                            .map(escapeHTML).join(", ")}</td>
                        <td>
                            <span class="status-badge ${medication.is_active ? "taken" : "missed"}">
                                ${medication.is_active ? "Active" : "Inactive"}
                            </span>
                        </td>
                        <td>
                            ${
                                state.user.role === "patient" && medication.is_active
                                    ? `<button class="text-button deactivate-medication"
                                               data-id="${medication.id}">
                                            Deactivate
                                       </button>`
                                    : "—"
                            }
                        </td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

async function confirmDose(doseId) {
    const notes = window.prompt(
        "Optional: Add a note about this confirmation.",
        ""
    );

    if (notes === null) return;

    try {
        const result = await api(`/medications/doses/${doseId}/confirm`, {
            method: "POST",
            body: { notes }
        });

        showToast(result.message || "Confirmation recorded.");

        await loadDashboard();
        await loadMedications();

    } catch (error) {
        showToast(error.message, "error");
    }
}

function showMedicationForm() {
    if (state.user.role !== "patient") {
        showToast("Medication management is restricted to the patient account in this interface.", "error");
        return;
    }

    showModal("Add medication", `
        <form id="medicationForm" class="modal-form">
            <label>Medication name</label>
            <input name="name" required maxlength="150"
                   placeholder="e.g. Vitamin D">

            <label>Dosage</label>
            <input name="dosage" required maxlength="100"
                   placeholder="e.g. 1 tablet">

            <label>Instructions</label>
            <textarea name="instructions" maxlength="1000"
                      placeholder="Optional instructions"></textarea>

            <label>Frequency</label>
            <select name="frequency">
                <option value="Daily">Daily</option>
                <option value="Twice daily">Twice daily</option>
                <option value="Weekly">Weekly</option>
                <option value="As prescribed">As prescribed</option>
            </select>

            <label>Schedule times</label>
            <input name="schedule_times" type="text" required
                   placeholder="08:00, 20:00">

            <small>Use 24-hour time. Separate multiple times with commas.</small>

            <label>Start date</label>
            <input name="start_date" type="date"
                   value="${localDateString()}" required>

            <label>End date (optional)</label>
            <input name="end_date" type="date">

            <label>Grace period (minutes)</label>
            <input name="grace_period_minutes" type="number"
                   min="0" max="1440" value="30">

            <button class="btn btn-primary btn-full" type="submit">
                Save medication
            </button>
        </form>
    `);
}

async function saveMedication(event) {
    event.preventDefault();

    const form = event.target;
    const values = new FormData(form);

    const scheduleTimes = String(values.get("schedule_times"))
        .split(",")
        .map((time) => time.trim())
        .filter(Boolean);

    if (!scheduleTimes.length ||
        scheduleTimes.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) {
        showToast("Enter valid times such as 08:00 or 20:00.", "error");
        return;
    }

    const payload = {
        name: values.get("name").trim(),
        dosage: values.get("dosage").trim(),
        instructions: values.get("instructions").trim(),
        frequency: values.get("frequency"),
        schedule_times: scheduleTimes,
        start_date: values.get("start_date"),
        end_date: values.get("end_date") || null,
        grace_period_minutes: Number(values.get("grace_period_minutes"))
    };

    try {
        const result = await api("/medications", {
            method: "POST",
            body: payload
        });

        closeModal();
        showToast(result.message || "Medication added.");

        await refreshAll();

    } catch (error) {
        showToast(error.message, "error");
    }
}

async function deactivateMedication(id) {
    if (!window.confirm("Deactivate this medication? Its history will be preserved.")) {
        return;
    }

    try {
        const result = await api(`/medications/${id}`, {
            method: "DELETE"
        });

        showToast(result.message);
        await refreshAll();

    } catch (error) {
        showToast(error.message, "error");
    }
}

/* =========================================================
   APPOINTMENTS
========================================================= */

async function loadAppointments() {
    const result = await api("/appointments");

    state.appointments = result.appointments || [];

    renderAppointments();
}

function renderAppointmentCard(appointment, allowCancel = false) {
    return `
        <div class="appointment-row">
            <div>
                <strong>${escapeHTML(appointment.doctor_name)}</strong>
                <small>${escapeHTML(appointment.specialty || "Medical appointment")}</small>
                <small>${formatDateTime(appointment.appointment_at)}</small>
                <small>${escapeHTML(appointment.location || "")}</small>
                ${
                    appointment.notes
                        ? `<small>${escapeHTML(appointment.notes)}</small>`
                        : ""
                }
            </div>

            ${
                allowCancel && appointment.status !== "cancelled"
                    ? `<button class="text-button cancel-appointment"
                               data-id="${appointment.id}">
                            Cancel
                       </button>`
                    : ""
            }
        </div>
    `;
}

function renderDashboardAppointments(appointments) {
    const container = $("#dashboardAppointments");

    container.innerHTML = appointments.length
        ? appointments.map((item) => renderAppointmentCard(item)).join("")
        : `<div class="empty-state">No upcoming appointments.</div>`;
}

function renderAppointments() {
    const container = $("#appointmentFullList");

    container.innerHTML = state.appointments.length
        ? state.appointments.map((item) =>
            renderAppointmentCard(item, state.user.role === "patient")
        ).join("")
        : `<div class="empty-state">No appointments found.</div>`;
}

function showAppointmentForm() {
    if (state.user.role !== "patient") {
        showToast("Only the patient account can manage appointments in this interface.", "error");
        return;
    }

    showModal("Add appointment", `
        <form id="appointmentForm" class="modal-form">
            <label>Doctor's name</label>
            <input name="doctor_name" required maxlength="150">

            <label>Specialty</label>
            <input name="specialty" maxlength="120"
                   placeholder="e.g. Cardiologist">

            <label>Location</label>
            <input name="location" maxlength="255"
                   placeholder="Clinic or hospital">

            <label>Date and time</label>
            <input name="appointment_at" type="datetime-local" required
                   min="${new Date().toISOString().slice(0, 16)}">

            <label>Notes</label>
            <textarea name="notes" maxlength="2000"></textarea>

            <button class="btn btn-primary btn-full" type="submit">
                Save appointment
            </button>
        </form>
    `);
}

async function saveAppointment(event) {
    event.preventDefault();

    const values = new FormData(event.target);
    const localDateTime = values.get("appointment_at");

    const appointmentDate = new Date(localDateTime);

    if (Number.isNaN(appointmentDate.getTime())) {
        showToast("Please enter a valid appointment date and time.", "error");
        return;
    }

    try {
        const result = await api("/appointments", {
            method: "POST",
            body: {
                doctor_name: values.get("doctor_name").trim(),
                specialty: values.get("specialty").trim() || null,
                location: values.get("location").trim() || null,
                appointment_at: appointmentDate.toISOString(),
                notes: values.get("notes").trim() || null
            }
        });

        closeModal();
        showToast(result.message || "Appointment created.");

        await refreshAll();

    } catch (error) {
        showToast(error.message, "error");
    }
}

async function cancelAppointment(id) {
    if (!window.confirm("Cancel this appointment?")) return;

    try {
        const result = await api(`/appointments/${id}`, {
            method: "DELETE"
        });

        showToast(result.message || "Appointment cancelled.");
        await refreshAll();

    } catch (error) {
        showToast(error.message, "error");
    }
}

/* =========================================================
   CARE TEAM
========================================================= */

async function loadCareTeam() {
    if (state.user.role !== "patient") return;

    const result = await api("/auth/members");

    state.members = result.members || [];

    renderCareTeam();
}

function renderCareTeam() {
    const container = $("#careTeamList");

    const activeMembers = state.members.filter((member) =>
        String(member.invitation_status).toLowerCase() !== "revoked"
    );

    if (!activeMembers.length) {
        container.innerHTML = `
            <div class="empty-state">
                No active family members or caretakers.
                You can invite someone to join your care team.
            </div>
        `;
        return;
    }

    container.innerHTML = activeMembers.map((member) => `
        <div class="care-member-row">
            <div>
                <strong>${escapeHTML(member.full_name)}</strong>
                <small>${escapeHTML(member.email)}</small>
                <small>
                    ${escapeHTML(member.role)} ·
                    ${escapeHTML(member.invitation_status)}
                </small>

                <small>
                    Profile: ${member.can_view_profile ? "Yes" : "No"} ·
                    Medications: ${member.can_view_medications ? "Yes" : "No"} ·
                    Confirm doses: ${member.can_confirm_doses ? "Yes" : "No"}
                </small>
            </div>

            <div>
                <button class="text-button edit-permissions"
                        data-id="${member.id}">
                    Permissions
                </button>

                <button class="text-button revoke-member"
                        data-id="${member.id}">
                    Revoke access
                </button>
            </div>
        </div>
    `).join("");
}

function showInviteForm() {
    if (state.user.role !== "patient") return;

    showModal("Invite a care team member", `
        <form id="inviteForm" class="modal-form">
            <label>Full name</label>
            <input name="full_name" required minlength="2" maxlength="120">

            <label>Email address</label>
            <input name="email" type="email" required>

            <label>Role</label>
            <select name="role">
                <option value="family">Family member</option>
                <option value="caretaker">Caretaker</option>
            </select>

            <p class="helper-note">
                Choose the permissions this person should receive.
                You can change them later.
            </p>

            ${permissionCheckboxes({
                can_view_profile: true,
                can_view_medications: true,
                can_manage_medications: false,
                can_confirm_doses: true,
                can_manage_appointments: false
            })}

            <button class="btn btn-primary btn-full" type="submit">
                Create invitation
            </button>
        </form>
    `);
}

function permissionCheckboxes(permissions) {
    const labels = {
        can_view_profile: "View patient profile",
        can_view_medications: "View medications",
        can_manage_medications: "Manage medications",
        can_confirm_doses: "Confirm doses",
        can_manage_appointments: "Manage appointments"
    };

    return Object.entries(labels).map(([key, label]) => `
        <label class="permission-option">
            <input type="checkbox" name="${key}"
                   ${permissions[key] ? "checked" : ""}>
            ${label}
        </label>
    `).join("");
}

function readPermissions(form) {
    const keys = [
        "can_view_profile",
        "can_view_medications",
        "can_manage_medications",
        "can_confirm_doses",
        "can_manage_appointments"
    ];

    return Object.fromEntries(
        keys.map((key) => [
            key,
            form.elements[key].checked
        ])
    );
}

async function saveInvitation(event) {
    event.preventDefault();

    const form = event.target;
    const values = new FormData(form);

    try {
        const result = await api("/auth/members/invite", {
            method: "POST",
            body: {
                full_name: values.get("full_name").trim(),
                email: values.get("email").trim(),
                role: values.get("role"),
                permissions: readPermissions(form)
            }
        });

        showModal("Invitation created", `
            <p>${escapeHTML(result.message)}</p>
            <p>Share this invitation token securely with the invited person:</p>
            <textarea id="invitationToken" readonly rows="4">${escapeHTML(result.invitation_token)}</textarea>
            <button id="copyInvitationToken" class="btn btn-primary btn-full" type="button">
                Copy invitation token
            </button>
            <p class="helper-note">
                The invitation has been created. This does not mean an email was sent.
                The invited person must accept it and create a passcode.
            </p>
        `);

        $("#copyInvitationToken").addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(result.invitation_token);
                showToast("Invitation token copied.");
            } catch {
                $("#invitationToken").select();
                showToast("Select and copy the token manually.", "error");
            }
        });

        await loadCareTeam();

    } catch (error) {
        showToast(error.message, "error");
    }
}

function showPermissionForm(id) {
    const member = state.members.find((item) => item.id === id);

    if (!member) return;

    showModal("Member permissions", `
        <form id="permissionForm" class="modal-form">
            <p>Update access for <strong>${escapeHTML(member.full_name)}</strong>.</p>

            ${permissionCheckboxes(member)}

            <button class="btn btn-primary btn-full" type="submit">
                Save permissions
            </button>
        </form>
    `);
}

async function savePermissions(event, memberId) {
    event.preventDefault();

    try {
        const result = await api(`/auth/members/${memberId}/permissions`, {
            method: "PUT",
            body: {
                permissions: readPermissions(event.target)
            }
        });

        closeModal();
        showToast(result.message);
        await loadCareTeam();

    } catch (error) {
        showToast(error.message, "error");
    }
}

async function revokeMember(id) {
    if (!window.confirm("Revoke this person's access to the care account?")) {
        return;
    }

    try {
        const result = await api(`/auth/members/${id}`, {
            method: "DELETE"
        });

        showToast(result.message);
        await loadCareTeam();

    } catch (error) {
        showToast(error.message, "error");
    }
}

/* =========================================================
   ACTIVITY
========================================================= */

function renderDashboardActivity(activities) {
    const container = $("#dashboardActivity");

    container.innerHTML = activities.length
        ? activities.map((item) => `
            <div class="activity-row">
                <strong>${escapeHTML(item.action)}</strong>
                <small>
                    ${escapeHTML(item.actor_name)}
                    (${escapeHTML(item.actor_role)})
                </small>
                <small>${formatDateTime(item.created_at)}</small>
            </div>
        `).join("")
        : `<div class="empty-state">No recent activity.</div>`;

    renderFullActivity(activities);
}


function renderFullActivity(activities) {
    const container = $("#fullActivityList");

    if (!activities || !activities.length) {
        container.innerHTML = `
            <div class="empty-state">
                No care history recorded yet.
            </div>
        `;
        return;
    }

    function getActivityInfo(item) {
        let details = {};

        try {
            details = typeof item.details === "string"
                ? JSON.parse(item.details)
                : (item.details || {});
        } catch {
            details = {};
        }

        const action = String(item.action || "").toLowerCase();
        const entity = String(item.entity_type || "").toLowerCase();

        if (action === "dose.confirmed") {
            return {
                category: "Medication",
                icon: "💊",
                title: "Medication dose confirmed",
                description: `Medication #${details.medication_id || item.entity_id} was marked as taken.`,
                extra: details.confirmation_type === "caregiver_reported"
                    ? "Reported by a caregiver"
                    : details.confirmation_type === "patient_self_reported"
                        ? "Reported by the patient"
                        : "Confirmation recorded"
            };
        }

        if (action === "appointment_created") {
            return {
                category: "Appointment",
                icon: "📅",
                title: "Appointment scheduled",
                description: details.doctor_name
                    ? `Appointment with ${details.doctor_name}`
                    : `Appointment #${item.entity_id} created`,
                extra: details.appointment_at
                    ? `Scheduled for ${formatDateTime(details.appointment_at)}`
                    : "Appointment details recorded"
            };
        }

        if (action === "appointment_cancelled") {
            return {
                category: "Appointment",
                icon: "✕",
                title: "Appointment cancelled",
                description: `Appointment #${item.entity_id} was cancelled.`,
                extra: "Previous status: " + (details.previous_status || "scheduled")
            };
        }

        if (action === "appointment_updated") {
            return {
                category: "Appointment",
                icon: "📅",
                title: "Appointment updated",
                description: `Appointment #${item.entity_id} was updated.`,
                extra: "Changes recorded in care history"
            };
        }

        if (entity === "dose_record") {
            return {
                category: "Medication",
                icon: "💊",
                title: "Medication record updated",
                description: `Dose record #${item.entity_id}`,
                extra: "Medication activity recorded"
            };
        }

        if (entity === "appointment") {
            return {
                category: "Appointment",
                icon: "📅",
                title: "Appointment activity",
                description: `Appointment #${item.entity_id}`,
                extra: "Appointment history updated"
            };
        }

        if (entity === "care_member") {
            return {
                category: "Care team",
                icon: "👥",
                title: "Care team updated",
                description: "A change was made to the care team.",
                extra: "Access and membership activity recorded"
            };
        }

        return {
            category: "Other",
            icon: "•",
            title: "Care activity recorded",
            description: `${item.action || "Activity"} · ${item.entity_type || "Record"} #${item.entity_id || "—"}`,
            extra: "Record preserved in care history"
        };
    }

    container.innerHTML = activities.map((item) => {
        const info = getActivityInfo(item);

        return `
            <article class="activity-card">
                <div class="activity-card-icon">
                    ${info.icon}
                </div>

                <div class="activity-card-content">
                    <div class="activity-card-header">
                        <span class="activity-category">
                            ${escapeHTML(info.category)}
                        </span>

                        <time>
                            ${escapeHTML(formatDateTime(item.created_at))}
                        </time>
                    </div>

                    <h3>${escapeHTML(info.title)}</h3>

                    <p class="activity-description">
                        ${escapeHTML(info.description)}
                    </p>

                    <small class="activity-extra">
                        ${escapeHTML(info.extra)}
                    </small>

                    <div class="activity-actor">
                        Recorded by
                        <strong>${escapeHTML(item.actor_name || "Unknown")}</strong>
                        · ${escapeHTML(item.actor_role || "User")}
                    </div>
                </div>
            </article>
        `;
    }).join("");
}


/* =========================================================
   EVENT HANDLERS
========================================================= */

function setupEvents() {
    $("#loginForm").addEventListener("submit", handleLogin);

    $("#logoutButton").addEventListener("click", logout);

    $("#closeModal").addEventListener("click", closeModal);

    $("#modalBackdrop").addEventListener("click", (event) => {
        if (event.target === $("#modalBackdrop")) closeModal();
    });

    $("#refreshDashboard").addEventListener("click", async () => {
        try {
            await refreshAll();
            showToast("Dashboard refreshed.");
        } catch (error) {
            showToast(error.message, "error");
        }
    });

    $("#addMedicationButton").addEventListener("click", showMedicationForm);
    $("#addAppointmentButton").addEventListener("click", showAppointmentForm);
    $("#inviteMemberButton").addEventListener("click", showInviteForm);

    $("#menuButton").addEventListener("click", () => {
        $("#sidebar").classList.toggle("mobile-open");
    });

    document.addEventListener("click", async (event) => {
        const pageButton = event.target.closest("[data-page]");

        if (pageButton) {
            navigate(pageButton.dataset.page);
            return;
        }

        const confirmButton = event.target.closest(".dose-confirm-button");

        if (confirmButton) {
            await confirmDose(Number(confirmButton.dataset.doseId));
            return;
        }

        const deactivateButton = event.target.closest(".deactivate-medication");

        if (deactivateButton) {
            await deactivateMedication(Number(deactivateButton.dataset.id));
            return;
        }

        const cancelButton = event.target.closest(".cancel-appointment");

        if (cancelButton) {
            await cancelAppointment(Number(cancelButton.dataset.id));
            return;
        }

        const permissionButton = event.target.closest(".edit-permissions");

        if (permissionButton) {
            showPermissionForm(Number(permissionButton.dataset.id));
            return;
        }

        const revokeButton = event.target.closest(".revoke-member");

        if (revokeButton) {
            await revokeMember(Number(revokeButton.dataset.id));
        }
    });

    $("#modalContent").addEventListener("submit", async (event) => {
        if (event.target.id === "medicationForm") {
            await saveMedication(event);
        }

        if (event.target.id === "appointmentForm") {
            await saveAppointment(event);
        }

        if (event.target.id === "inviteForm") {
            await saveInvitation(event);
        }

        if (event.target.id === "permissionForm") {
            const memberId = Number(
                state.members.find((member) =>
                    $("#modalTitle").textContent === "Member permissions"
                        ? member.id === Number(
                            document.querySelector(".edit-permissions")?.dataset.id
                        )
                        : false
                )?.id
            );

            if (memberId) await savePermissions(event, memberId);
        }
    });
}

/* =========================================================
   STARTUP
========================================================= */

async function initialize() {
    setupLoginModes();
    setupEvents();

    try {
        await loadApplication();
    } catch (error) {
        showLogin();
    }
}

document.addEventListener("DOMContentLoaded", initialize);
