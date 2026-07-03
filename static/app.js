// Global Chart & Cache References
let cashFlowChart = null;
let historicalChart = null;
let projectionChart = null;
let csvParsedRows = [];
let currentDebts = [];
let currentSavings = [];
let currentFixed = [];
let currentDiscretionary = [];
let debtCurrentPage = 1;
const debtRowsPerPage = 5;

// Global fetch interceptor for 401 Unauthorized
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        showLoginScreen();
    }
    return response;
};

function showLoginScreen() {
    document.getElementById("login-container").style.display = "flex";
    document.getElementById("app-container").style.display = "none";
}

function showAppScreen(username) {
    document.getElementById("login-container").style.display = "none";
    document.getElementById("app-container").style.display = "block";
    
    // Update profile display
    if (username) {
        document.getElementById("user-display-name").innerText = username;
        document.getElementById("user-avatar").innerText = username.charAt(0).toUpperCase();
    }
}

async function checkAuthStatus() {
    try {
        const response = await originalFetch("/api/auth/me");
        if (response.ok) {
            const data = await response.json();
            showAppScreen(data.username);
            fetchDashboardData();
            fetchTransactions();
        } else {
            showLoginScreen();
        }
    } catch (e) {
        showLoginScreen();
    }
}

function toggleAuthForm(e) {
    if (e) e.preventDefault();
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const subtitle = document.getElementById("auth-subtitle");
    const toggleMsg = document.getElementById("auth-toggle-msg");
    const toggleLink = document.getElementById("auth-toggle-link");
    
    if (loginForm.classList.contains("hidden")) {
        loginForm.classList.remove("hidden");
        registerForm.classList.add("hidden");
        subtitle.innerText = "Log in to manage your personal finances securely";
        toggleMsg.innerText = "Don't have an account?";
        toggleLink.innerText = "Register now";
    } else {
        loginForm.classList.add("hidden");
        registerForm.classList.remove("hidden");
        subtitle.innerText = "Create a new account to get started";
        toggleMsg.innerText = "Already have an account?";
        toggleLink.innerText = "Log in";
    }
}

async function handleAuthSubmit(event, action) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = {};
    formData.forEach((value, key) => {
        payload[key] = value;
    });
    
    try {
        const endpoint = action === 'login' ? '/api/auth/login' : '/api/auth/register';
        const response = await originalFetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Authentication failed.");
        }
        
        const data = await response.json();
        if (action === 'login') {
            showAppScreen(data.username);
            fetchDashboardData();
            fetchTransactions();
            form.reset();
        } else {
            alert(data.message);
            toggleAuthForm();
            document.getElementById("login-username").value = payload.username;
            document.getElementById("login-password").value = "";
        }
    } catch (e) {
        alert(e.message);
    }
}

async function handleLogout() {
    try {
        await originalFetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
        console.error("Logout error:", e);
    }
    showLoginScreen();
}

async function fetchMonths() {
    try {
        const response = await fetch("/api/months");
        if (!response.ok) throw new Error("Failed to fetch available months.");
        const months = await response.json();
        
        const select = document.getElementById("dashboard-month-select");
        const currentVal = select.value;
        select.innerHTML = `<option value="">All Time</option>`;
        
        months.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.innerText = formatMonthName(m);
            select.appendChild(opt);
        });
        
        if (months.includes(currentVal)) {
            select.value = currentVal;
        }
    } catch (e) {
        console.error("Error fetching months:", e);
    }
}

function formatMonthName(mStr) {
    const [y, m] = mStr.split("-");
    const date = new Date(parseInt(y), parseInt(m) - 1, 1);
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function onMonthChange() {
    fetchDashboardData();
    fetchTransactions();
}

async function fetchHistoricalReports() {
    try {
        const response = await fetch("/api/reports/historical");
        if (!response.ok) throw new Error("Failed to fetch historical reports.");
        const data = await response.json();
        
        const ctx = document.getElementById('historicalChart').getContext('2d');
        if (historicalChart) historicalChart.destroy();
        
        const labels = data.map(r => formatMonthName(r.month));
        const incomeData = data.map(r => r.income);
        const spendingData = data.map(r => r.spending);
        const savingsData = data.map(r => r.savings);
        const netFlowData = data.map(r => r.net_cash_flow);
        
        historicalChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Income',
                        data: incomeData,
                        backgroundColor: '#10b981',
                        borderColor: '#10b981',
                        borderWidth: 1
                    },
                    {
                        label: 'Spending',
                        data: spendingData,
                        backgroundColor: '#ef4444',
                        borderColor: '#ef4444',
                        borderWidth: 1
                    },
                    {
                        label: 'Savings',
                        data: savingsData,
                        backgroundColor: '#6366f1',
                        borderColor: '#6366f1',
                        borderWidth: 1
                    },
                    {
                        label: 'Net Surplus',
                        data: netFlowData,
                        type: 'line',
                        borderColor: '#38bdf8',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        tension: 0.1,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#f3f4f6', font: { family: 'Outfit' } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#f3f4f6', font: { family: 'Outfit' } }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#f3f4f6',
                            font: { family: 'Outfit', size: 12 }
                        }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Historical Report Error:", e);
    }
}

async function showProcessMonthModal() {
    const monthSelect = document.getElementById("dashboard-month-select");
    const selectedMonth = monthSelect ? monthSelect.value : "";
    if (!selectedMonth) {
        alert("Please select a specific month from the 'View Month' dropdown first.");
        return;
    }
    
    try {
        const response = await fetch(`/api/dashboard?month=${selectedMonth}`);
        if (!response.ok) throw new Error("Failed to load month metrics.");
        const data = await response.json();
        
        const income = data.actuals.income;
        const totalOutflows = data.actuals.fixed + data.actuals.discretionary + data.actuals.savings + data.actuals.debt_payments;
        const surplus = Math.max(0, income - totalOutflows);
        
        document.getElementById("process-month-name").value = selectedMonth;
        document.getElementById("process-month-surplus").value = surplus.toFixed(2);
        
        const select = document.getElementById("process-month-savings-select");
        select.innerHTML = "";
        
        if (data.savings.length === 0) {
            select.innerHTML = `<option value="">-- No Savings Account Found --</option>`;
        } else {
            data.savings.forEach(acc => {
                const opt = document.createElement("option");
                opt.value = acc.id;
                opt.innerText = `${acc.account_name} (Bal: $${acc.current_balance.toFixed(2)})`;
                select.appendChild(opt);
            });
        }
        
        showModal('process-month-modal');
    } catch (e) {
        alert("Error loading rollover data: " + e.message);
    }
}

async function handleProcessMonthSubmit(event) {
    event.preventDefault();
    const month = document.getElementById("process-month-name").value;
    const surplus = parseFloat(document.getElementById("process-month-surplus").value);
    const savingsId = parseInt(document.getElementById("process-month-savings-select").value);
    
    if (!savingsId) {
        alert("Please select a destination savings account.");
        return;
    }
    
    if (surplus <= 0) {
        alert("There is no positive net cash flow surplus to roll over for this month.");
        return;
    }
    
    try {
        const response = await fetch("/api/months/process", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                month: month,
                savings_account_id: savingsId,
                amount: surplus
            })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Rollover failed.");
        }
        
        const data = await response.json();
        alert(data.message);
        closeModal('process-month-modal');
        
        fetchDashboardData();
        fetchTransactions();
    } catch (e) {
        alert("Rollover Error: " + e.message);
    }
}

// Initialize Dashboard on Load
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    checkAuthStatus();
});

// ----------------- NAVIGATION -----------------
function initNavigation() {
    document.querySelectorAll(".nav-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-view").forEach(v => v.classList.remove("active"));

    const activeBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
    const activeView = document.getElementById(`view-${tabId}`);
    
    if (activeBtn) activeBtn.classList.add("active");
    if (activeView) activeView.classList.add("active");

    // Update Top Header Title
    const titles = {
        'overview': 'Financial Dashboard',
        'income-spend': 'Income & Spending Manager',
        'debts': 'Debt & Liabilities Tracker',
        'savings': 'Savings & Growth Forecasts',
        'etl': 'CSV ETL Statement Ingestion'
    };
    document.getElementById("page-title").innerText = titles[tabId] || 'Financial Dashboard';
}

// ----------------- DATA FETCHING & POPULATION -----------------
async function fetchDashboardData() {
    try {
        const monthSelect = document.getElementById("dashboard-month-select");
        const selectedMonth = monthSelect ? monthSelect.value : "";
        const url = selectedMonth ? `/api/dashboard?month=${selectedMonth}` : "/api/dashboard";
        
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch dashboard summaries.");
        const data = await response.json();
        
        // Cache current items
        currentDebts = data.debts;
        currentSavings = data.savings;
        currentFixed = data.fixed_spending_items;
        currentDiscretionary = data.discretionary_spending_items;
        
        // 1. Populate KPIs
        updateKPIs(data.summary);
        
        // 2. Render Charts & Lists
        renderCashFlowChart(data.summary);
        renderDebtProgress(data.debts);
        renderBudgetVsActual(data.summary, data.actuals);
        
        // 3. Populate Tabs Data
        populateIncomeTab(data.income);
        populateFixedSpendingTab(data.fixed_spending_items, data.debts, data.actuals);
        populateDiscretionarySpendingTab(data.discretionary_spending_items, data.actuals);
        populateDebtsTab(data.debts);
        populateSavingsTab(data.savings);
        
        // 4. Run Payoff Calculations
        calculatePayoffTimelines(data.debts);

        // 5. Populate Months & Historical Reports (Only if not currently processing to avoid loop)
        if (!window._isRefreshingMonths) {
            window._isRefreshingMonths = true;
            await fetchMonths();
            await fetchHistoricalReports();
            window._isRefreshingMonths = false;
        }

    } catch (error) {
        console.error("Dashboard Loading Error:", error);
        window._isRefreshingMonths = false;
    }
}

function updateKPIs(summary) {
    const format = val => {
        const prefix = val < 0 ? "-" : "";
        return prefix + "$" + Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    
    document.getElementById("kpi-net-worth").innerText = format(summary.net_worth);
    document.getElementById("kpi-income").innerText = format(summary.total_income);
    
    // Obligations include Fixed (unlinked) + Discretionary + Debt Payments + Savings contributions
    const totalObligations = summary.fixed_spending + summary.discretionary_spending + summary.debt_obligations + summary.savings_contributions;
    document.getElementById("kpi-obligations").innerText = format(totalObligations);
    
    const cashFlowEl = document.getElementById("kpi-cash-flow");
    cashFlowEl.innerText = format(summary.net_remaining_cash_flow);
    
    // Update cash flow indicator styling
    if (summary.net_remaining_cash_flow >= 0) {
        cashFlowEl.className = "kpi-value text-emerald";
    } else {
        cashFlowEl.className = "kpi-value text-red";
    }
}

// ----------------- CHART GENERATION -----------------
function renderCashFlowChart(summary) {
    const ctx = document.getElementById('cashFlowChart').getContext('2d');
    
    // Destroy previous instance to re-render
    if (cashFlowChart) cashFlowChart.destroy();
    
    const totalOut = summary.fixed_spending + summary.discretionary_spending + summary.debt_obligations + summary.savings_contributions;
    const remaining = Math.max(0, summary.total_income - totalOut);
    
    cashFlowChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Fixed Spending', 'Discretionary', 'Debt Payments', 'Savings contributions', 'Unallocated Remaining'],
            datasets: [{
                data: [
                    summary.fixed_spending,
                    summary.discretionary_spending,
                    summary.debt_obligations,
                    summary.savings_contributions,
                    remaining
                ],
                backgroundColor: [
                    '#ef4444', // Fixed
                    '#f59e0b', // Discretionary
                    '#a855f7', // Debt Payments
                    '#6366f1', // Savings
                    '#10b981'  // Remaining
                ],
                borderColor: '#161f30',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#f3f4f6',
                        font: { family: 'Outfit', size: 12 }
                    }
                }
            }
        }
    });
}

// Render Debt Payoff Progress Meters on Overview Tab
function renderDebtProgress(debts) {
    const container = document.getElementById("debt-progress-container");
    container.innerHTML = "";
    
    if (debts.length === 0) {
        container.innerHTML = `<p class="text-muted">No debt data available. Add accounts inside Debt Tracker.</p>`;
        return;
    }
    
    debts.forEach(d => {
        let percent = 0;
        let original = d.original_amount;
        
        if (d.debt_type === 'Credit Card') {
            original = d.total_credit_line || (d.current_balance * 1.5);
            percent = original > 0 ? (1 - (d.current_balance / original)) * 100 : 0;
        } else {
            percent = original > 0 ? (1 - (d.current_balance / original)) * 100 : 0;
        }
        
        percent = Math.max(0, Math.min(100, Math.round(percent)));
        
        const item = document.createElement("div");
        item.className = "progress-item";
        item.style.cursor = "pointer";
        item.title = "Click to scroll to and edit this account";
        item.onclick = () => scrollToAndEditDebt(d.id);
        item.innerHTML = `
            <div class="progress-info">
                <span><strong>${d.account_name}</strong> (${d.debt_type})</span>
                <span>$${d.current_balance.toLocaleString()} remaining / ${percent}% paid</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${percent}%"></div>
            </div>
        `;
        container.appendChild(item);
    });
}

// ----------------- TAB POPULATORS -----------------
function populateIncomeTab(income) {
    const tbody = document.getElementById("income-table-body");
    tbody.innerHTML = "";
    income.forEach(item => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${item.source_name}</strong></td>
            <td>${item.recipient}</td>
            <td>${item.frequency}</td>
            <td>$${item.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>
                <button class="action-btn" onclick="deleteItem('/api/income/${item.id}')">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function populateFixedSpendingTab(fixed, debts, actuals) {
    const tbody = document.getElementById("fixed-table-body");
    tbody.innerHTML = "";
    
    // Update link-debt selector inside fixed-spending modals (both add and edit)
    const linkSelect = document.getElementById("fixed-link-debt-select");
    linkSelect.innerHTML = `<option value="">-- None --</option>`;
    
    const editLinkSelect = document.getElementById("edit-fixed-link-debt-select");
    if (editLinkSelect) {
        editLinkSelect.innerHTML = `<option value="">-- None --</option>`;
    }
    
    const manualLinkSelect = document.getElementById("manual-tx-link-debt-select");
    if (manualLinkSelect) {
        manualLinkSelect.innerHTML = `<option value="">-- None --</option>`;
    }
    
    debts.forEach(d => {
        const opt = `<option value="${d.id}">${d.account_name}</option>`;
        linkSelect.innerHTML += opt;
        if (editLinkSelect) {
            editLinkSelect.innerHTML += opt;
        }
        if (manualLinkSelect) {
            manualLinkSelect.innerHTML += opt;
        }
    });

    fixed.forEach(item => {
        const tr = document.createElement("tr");
        const linkedText = item.linked_debt_id ? ` <span class="badge" style="background:#a855f7; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px;">Linked</span>` : "";
        
        const actualSpend = item.actual_spent || 0.0;
        const budget = item.monthly_amount;
        const colorStyle = actualSpend > budget ? "color: #ef4444; font-weight: 500;" : "color: #10b981;";
        
        tr.innerHTML = `
            <td><strong>${item.category}</strong></td>
            <td>${item.subcategory}${linkedText}</td>
            <td>$${budget.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td style="${colorStyle}">$${actualSpend.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="action-btn" style="color: var(--primary);" onclick="showEditFixedModal(${item.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="action-btn" onclick="deleteItem('/api/fixed/${item.id}')">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function populateDiscretionarySpendingTab(discretionary, actuals) {
    const tbody = document.getElementById("discretionary-table-body");
    tbody.innerHTML = "";
    discretionary.forEach(item => {
        const tr = document.createElement("tr");
        
        const actualSpend = item.actual_spent || 0.0;
        const budget = item.monthly_amount;
        const colorStyle = actualSpend > budget ? "color: #ef4444; font-weight: 500;" : "color: #10b981;";
        
        tr.innerHTML = `
            <td><strong>${item.category}</strong></td>
            <td>${item.subcategory}</td>
            <td>$${budget.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td style="${colorStyle}">$${actualSpend.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="action-btn" style="color: var(--primary);" onclick="showEditDiscretionaryModal(${item.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="action-btn" onclick="deleteItem('/api/discretionary/${item.id}')">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function populateDebtsTab(debts) {
    const tbody = document.getElementById("debts-table-body");
    tbody.innerHTML = "";
    
    const totalItems = debts.length;
    const totalPages = Math.ceil(totalItems / debtRowsPerPage) || 1;
    
    // Ensure current page is in bounds
    if (debtCurrentPage > totalPages) {
        debtCurrentPage = totalPages;
    }
    if (debtCurrentPage < 1) {
        debtCurrentPage = 1;
    }
    
    const startIndex = (debtCurrentPage - 1) * debtRowsPerPage;
    const endIndex = Math.min(startIndex + debtRowsPerPage, totalItems);
    const paginatedDebts = debts.slice(startIndex, endIndex);
    
    paginatedDebts.forEach(d => {
        const tr = document.createElement("tr");
        tr.id = `debt-row-${d.id}`;
        const rateText = d.interest_rate ? `${d.interest_rate}%` : 'N/A';
        const detailsText = d.debt_type === 'Credit Card' 
            ? `Limit: $${d.total_credit_line.toLocaleString()}` 
            : `Payments: ${d.remaining_payments} mos`;
        
        const actualPay = d.actual_payment || 0.0;
        const targetPay = d.monthly_payment;
        const colorStyle = actualPay >= targetPay ? "color: #10b981; font-weight: 500;" : "color: #9ca3af;";
        
        tr.innerHTML = `
            <td><strong>${d.account_name}</strong></td>
            <td>${d.institution}</td>
            <td>${d.debt_type}</td>
            <td>$${d.current_balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>${rateText}</td>
            <td>$${targetPay.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td style="${colorStyle}">$${actualPay.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td><small class="text-muted">${detailsText}</small></td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="action-btn" style="color: var(--primary);" onclick="showEditDebtModal(${d.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="action-btn" onclick="deleteItem('/api/debts/${d.id}')">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    renderDebtsPagination(totalItems, totalPages);
}

function populateSavingsTab(savings) {
    const tbody = document.getElementById("savings-table-body");
    tbody.innerHTML = "";
    
    // Update Forecast Select options
    const select = document.getElementById("forecast-account-select");
    const prevVal = select.value;
    select.innerHTML = "";
    
    savings.forEach(s => {
        const tr = document.createElement("tr");
        tr.id = `savings-row-${s.id}`;
        const actualContrib = s.actual_contribution || 0.0;
        const targetContrib = s.monthly_contribution;
        const colorStyle = actualContrib >= targetContrib ? "color: #10b981; font-weight: 500;" : "color: #9ca3af;";
        
        tr.innerHTML = `
            <td><strong>${s.account_name}</strong></td>
            <td>${s.account_type}</td>
            <td>$${targetContrib.toLocaleString(undefined, {minimumFractionDigits: 2})}/mo</td>
            <td style="${colorStyle}">$${actualContrib.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>$${s.current_balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>${s.annual_yield}%</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="action-btn" style="color: var(--primary);" onclick="showEditSavingsModal(${s.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="action-btn" onclick="deleteItem('/api/savings/${s.id}')">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
        
        select.innerHTML += `<option value="${s.account_name}">${s.account_name}</option>`;
    });

    if (savings.length > 0) {
        select.value = prevVal && select.querySelector(`option[value="${prevVal}"]`) ? prevVal : savings[0].account_name;
        runForecast();
    } else {
        if (projectionChart) projectionChart.destroy();
    }
}

// ----------------- FORECAST CALCULATOR (Chart.js) -----------------
async function runForecast() {
    const name = document.getElementById("forecast-account-select").value;
    const years = document.getElementById("forecast-years").value;
    if (!name) return;
    
    try {
        const response = await fetch(`/api/projection?account_name=${encodeURIComponent(name)}&years=${years}`);
        if (!response.ok) throw new Error("Forecast failed.");
        const projection = await response.json();
        
        renderProjectionChart(projection);
    } catch (e) {
        console.error(e);
    }
}

function renderProjectionChart(data) {
    const ctx = document.getElementById('projectionChart').getContext('2d');
    if (projectionChart) projectionChart.destroy();
    
    const labels = data.map(item => `Yr ${item.year}`);
    const balances = data.map(item => item.projected_balance);
    
    projectionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Projected Portfolio Balance',
                data: balances,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 3,
                pointBackgroundColor: '#6366f1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9ca3af', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9ca3af', font: { family: 'Outfit' } }
                }
            }
        }
    });
}

// ----------------- DEBT SNOWBALL CALCULATION (CLIENT SIDE) -----------------
function calculatePayoffTimelines(debtsList) {
    if (!debtsList || debtsList.length === 0) {
        document.getElementById("standard-payoff-time").innerText = "No debt";
        document.getElementById("standard-payoff-interest").innerText = "Total Interest paid: $0.00";
        document.getElementById("snowball-payoff-time").innerText = "No debt";
        document.getElementById("snowball-payoff-interest").innerText = "Total Interest paid: $0.00";
        return;
    }
    
    const extraBudget = parseFloat(document.getElementById("payoff-extra-input").value) || 0;
    
    // Simulate standard payments (Min payments only)
    let standardMonths = 0;
    let standardInterestTotal = 0;
    let tempDebtsStd = debtsList.map(d => ({
        balance: d.current_balance,
        minPay: d.monthly_payment,
        rate: (d.interest_rate || 0) / 100 / 12
    }));

    // Limit simulation loops to 1000 months to prevent freezes
    while (tempDebtsStd.some(d => d.balance > 0) && standardMonths < 600) {
        standardMonths++;
        tempDebtsStd.forEach(d => {
            if (d.balance > 0) {
                let interest = d.balance * d.rate;
                standardInterestTotal += interest;
                d.balance += interest;
                let payment = Math.min(d.balance, d.minPay);
                d.balance -= payment;
            }
        });
    }

    // Simulate Snowball strategy (Lowest Balance First gets the rollover + extra)
    let snowballMonths = 0;
    let snowballInterestTotal = 0;
    let tempDebtsSnow = debtsList.map(d => ({
        balance: d.current_balance,
        minPay: d.monthly_payment,
        rate: (d.interest_rate || 0) / 100 / 12
    }));

    while (tempDebtsSnow.some(d => d.balance > 0) && snowballMonths < 600) {
        snowballMonths++;
        
        // Sort lowest balance first for Snowball payoff allocation
        let activeDebts = tempDebtsSnow
            .map((d, index) => ({d, index}))
            .filter(item => item.d.balance > 0)
            .sort((a, b) => a.d.balance - b.d.balance);

        if (activeDebts.length === 0) break;
        
        // Total monthly budget is sum of all active min payments + extra budget
        let totalAvailBudget = extraBudget;
        
        // Determine total minimum payment sum
        tempDebtsSnow.forEach(d => {
            if (d.balance > 0) {
                totalAvailBudget += d.minPay;
            }
        });
        
        // First accrue interest on all active debts
        activeDebts.forEach(item => {
            let interest = item.d.balance * item.d.rate;
            snowballInterestTotal += interest;
            item.d.balance += interest;
        });

        // Pay min payment first to all active debts
        let remainingBudget = totalAvailBudget;
        activeDebts.forEach(item => {
            let minToPay = Math.min(item.d.balance, item.d.minPay);
            item.d.balance -= minToPay;
            remainingBudget -= minToPay;
        });

        // Apply remaining budget (extra money + rolled over mins) to the smallest debt
        if (remainingBudget > 0 && activeDebts.length > 0) {
            let target = activeDebts[0].d; // Smallest active debt
            let extraToPay = Math.min(target.balance, remainingBudget);
            target.balance -= extraToPay;
        }
    }

    // Format Outputs
    const fmtYears = mos => {
        if (mos >= 600) return "50+ Years (Interest trap)";
        const yrs = Math.floor(mos / 12);
        const m = mos % 12;
        return `${yrs} yrs, ${m} mos`;
    };
    
    document.getElementById("standard-payoff-time").innerText = fmtYears(standardMonths);
    document.getElementById("standard-payoff-interest").innerText = `Total Interest paid: $${standardInterestTotal.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    
    document.getElementById("snowball-payoff-time").innerText = fmtYears(snowballMonths);
    document.getElementById("snowball-payoff-interest").innerText = `Total Interest paid: $${snowballInterestTotal.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
}

// ----------------- CRUD API FORM ACTIONS -----------------
async function handleCRUDSubmit(event, endpoint, modalId) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    // Convert form fields to JSON payload
    const payload = {};
    formData.forEach((value, key) => {
        // Parse floats and ints if possible
        if (value === "") {
            payload[key] = null;
        } else if (!isNaN(value) && key !== "recipient" && key !== "frequency" && key !== "debt_type" && key !== "account_type" && key !== "category") {
            payload[key] = parseFloat(value);
        } else {
            payload[key] = value;
        }
    });

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Submission failed.");
        }
        
        form.reset();
        closeModal(modalId);
        fetchDashboardData();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function deleteItem(endpoint) {
    if (!confirm("Are you sure you want to delete this item?")) return;
    try {
        const response = await fetch(endpoint, { method: 'DELETE' });
        if (!response.ok) throw new Error("Delete request failed.");
        fetchDashboardData();
    } catch (e) {
        alert(e.message);
    }
}

// ----------------- ETL statement IMPORT LOGIC -----------------
function parseCSVHeaders(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split("\n");
        if (lines.length === 0) return;
        
        // Extract headers from first CSV line
        const headers = lines[0].split(",").map(h => h.trim().replace(/^"|"$/g, ''));
        
        // Show Mapping Selectors
        const mappingDiv = document.getElementById("column-mapping-section");
        mappingDiv.style.display = "block";
        
        // Populate selectors
        ['map-date', 'map-desc', 'map-amount', 'map-category'].forEach(selectId => {
            const select = document.getElementById(selectId);
            select.innerHTML = selectId === 'map-category' ? '<option value="">-- Auto-Categorize --</option>' : '';
            headers.forEach(h => {
                const opt = document.createElement("option");
                opt.value = h;
                opt.innerText = h;
                
                // Smart auto-matching default selection
                if (selectId === 'map-date' && h.toLowerCase().includes('date')) opt.selected = true;
                if (selectId === 'map-desc' && (h.toLowerCase().includes('desc') || h.toLowerCase().includes('name') || h.toLowerCase().includes('payee'))) opt.selected = true;
                if (selectId === 'map-amount' && h.toLowerCase().includes('amount')) opt.selected = true;
                if (selectId === 'map-category' && (h.toLowerCase().includes('cat') || h.toLowerCase().includes('group') || h.toLowerCase().includes('type'))) opt.selected = true;
                
                select.appendChild(opt);
            });
        });
        
        // Generate Preview rows
        const previewHead = document.getElementById("csv-preview-head");
        const previewBody = document.getElementById("csv-preview-body");
        
        previewHead.innerHTML = `<tr>${headers.slice(0,4).map(h => `<th>${h}</th>`).join("")}</tr>`;
        previewBody.innerHTML = "";
        
        lines.slice(1, 6).forEach(line => {
            if (!line.trim()) return;
            const cols = line.split(",").map(c => c.trim().replace(/^"|"$/g, ''));
            previewBody.innerHTML += `<tr>${cols.slice(0, 4).map(c => `<td>${c}</td>`).join("")}</tr>`;
        });
    };
    reader.readAsText(file);
}

async function handleETLSubmit(event) {
    event.preventDefault();
    const fileInput = document.getElementById("etl-file");
    const file = fileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("date_col", document.getElementById("map-date").value);
    formData.append("desc_col", document.getElementById("map-desc").value);
    formData.append("amount_col", document.getElementById("map-amount").value);
    formData.append("category_col", document.getElementById("map-category").value);
    
    try {
        const response = await fetch("/api/etl/import", {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "ETL Process failed.");
        }
        
        const res = await response.json();
        alert(`ETL Import Pipeline Complete!\nParsed and Ingested: ${res.inserted} transactions\nDuplicate logs skipped: ${res.skipped_duplicates}`);
        
        // Reset Ingestion Tab form
        document.getElementById("etl-form").reset();
        document.getElementById("column-mapping-section").style.display = "none";
        document.getElementById("csv-preview-head").innerHTML = `<tr><th>Choose file to preview...</th></tr>`;
        document.getElementById("csv-preview-body").innerHTML = "";
        
        // Update Dashboard Data & Ledger view
        fetchDashboardData();
        fetchTransactions();
        
        // Navigate user back to Dashboard tab to review
        switchTab("overview");
        
    } catch (e) {
        alert("ETL Error: " + e.message);
    }
}

async function fetchTransactions() {
    try {
        const monthSelect = document.getElementById("dashboard-month-select");
        const selectedMonth = monthSelect ? monthSelect.value : "";
        const url = selectedMonth ? `/api/transactions?month=${selectedMonth}` : "/api/transactions";
        
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch ledger logs.");
        const transactions = await response.json();
        
        const dashboardBody = document.getElementById("dashboard-tx-table-body");
        const ledgerBody = document.getElementById("ledger-table-body");
        
        dashboardBody.innerHTML = "";
        ledgerBody.innerHTML = "";
        
        if (transactions.length === 0) {
            dashboardBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No transactions found.</td></tr>`;
            ledgerBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No transactions found.</td></tr>`;
            return;
        }
        
        // Populate Overview Dashboard (Limit to 5 recent items)
        transactions.slice(0, 5).forEach(tx => {
            const tr = document.createElement("tr");
            const amtText = tx.amount < 0 
                ? `<span class="text-red">-$${Math.abs(tx.amount).toFixed(2)}</span>` 
                : `<span class="text-emerald">+$${tx.amount.toFixed(2)}</span>`;
            
            tr.innerHTML = `
                <td>${tx.transaction_date}</td>
                <td><strong>${tx.description}</strong></td>
                <td>${amtText}</td>
                <td><span class="badge" style="background: rgba(99,102,241,0.15); color:#818cf8; padding: 2px 8px; border-radius: 6px; font-size:0.75rem;">${tx.category}</span></td>
            `;
            dashboardBody.appendChild(tr);
        });

        // Populate Dedicated ETL Ledger Logs Tab
        transactions.forEach(tx => {
            const tr = document.createElement("tr");
            const amtText = tx.amount < 0 
                ? `<span class="text-red">-$${Math.abs(tx.amount).toFixed(2)}</span>` 
                : `<span class="text-emerald">+$${tx.amount.toFixed(2)}</span>`;
            const fileText = tx.source_file ? tx.source_file.split("/").pop().replace("temp_upload_", "") : "Seed Inflow";
            
            tr.innerHTML = `
                <td>${tx.transaction_date}</td>
                <td><strong>${tx.description}</strong></td>
                <td>${amtText}</td>
                <td><span class="badge" style="background: rgba(99,102,241,0.15); color:#818cf8; padding: 2px 8px; border-radius: 6px; font-size:0.75rem;">${tx.category}</span></td>
                <td><small class="text-muted">${fileText}</small></td>
                <td>
                    <button class="action-btn" onclick="deleteTransaction(${tx.id})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            `;
            ledgerBody.appendChild(tr);
        });

    } catch (e) {
        console.error(e);
    }
}

async function clearTransactions() {
    if (!confirm("Are you sure you want to clear your imported transaction ledger logs?")) return;
    try {
        const response = await fetch("/api/transactions", { method: 'DELETE' });
        if (!response.ok) throw new Error("Failed to clear logs.");
        fetchTransactions();
        fetchDashboardData();
    } catch(e) {
        alert(e.message);
    }
}

async function clearAllData() {
    if (!confirm("⚠️ WARNING: This will completely clear all income, spending, savings, debt accounts, and transaction records. Are you sure you want to proceed?")) return;
    try {
        const response = await fetch("/api/clear-all", { method: 'DELETE' });
        if (!response.ok) throw new Error("Failed to clear database records.");
        alert("All application data has been successfully cleared.");
        fetchDashboardData();
        fetchTransactions();
    } catch(e) {
        alert(e.message);
    }
}

// ----------------- POPUP MODALS UTILITY FUNCTIONS -----------------
function showModal(modalId) {
    document.getElementById(modalId).classList.add("active");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
}

// Dynamically toggles fields in the Add Debt form based on category
function adjustDebtFormFields(debtType) {
    const ccField = document.getElementById("field-credit-line");
    const remField = document.getElementById("field-remaining-payments");
    const origField = document.getElementById("field-original-amount");
    const termField = document.getElementById("field-loan-length");
    const lendField = document.getElementById("field-lender-type");

    // Default: Reset all to hidden
    [ccField, remField, origField, termField, lendField].forEach(el => el.classList.add("hidden"));

    if (debtType === 'Credit Card') {
        ccField.classList.remove("hidden");
    } else if (debtType === 'BNPL') {
        remField.classList.remove("hidden");
        origField.classList.remove("hidden");
    } else if (debtType === 'Car Loan' || debtType === 'Mortgage') {
        termField.classList.remove("hidden");
        origField.classList.remove("hidden");
        remField.classList.remove("hidden");
    } else if (debtType === 'Personal Loan') {
        lendField.classList.remove("hidden");
        origField.classList.remove("hidden");
        rateField = document.querySelector("#add-debt-modal input[name='interest_rate']").parentElement;
    }
}

function renderBudgetVsActual(summary, actuals) {
    const tbody = document.getElementById("budget-vs-actual-tbody");
    
    // Update the actual outflow summary widgets (handling case where actuals is missing/empty)
    const outflowSpend = actuals ? ((actuals.fixed || 0.0) + (actuals.discretionary || 0.0)) : 0.0;
    const outflowPaid = actuals ? (actuals.debt_payments || 0.0) : 0.0;
    const outflowContributed = actuals ? (actuals.savings || 0.0) : 0.0;
    const outflowCombined = outflowSpend + outflowPaid + outflowContributed;

    const formatVal = val => {
        const prefix = val < 0 ? "-" : "";
        return prefix + "$" + Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const elSpend = document.getElementById("actual-outflow-spend");
    const elPaid = document.getElementById("actual-outflow-paid");
    const elContributed = document.getElementById("actual-outflow-contributed");
    const elCombined = document.getElementById("actual-outflow-combined");

    if (elSpend) elSpend.innerText = formatVal(outflowSpend);
    if (elPaid) elPaid.innerText = formatVal(outflowPaid);
    if (elContributed) elContributed.innerText = formatVal(outflowContributed);
    if (elCombined) elCombined.innerText = formatVal(outflowCombined);

    if (!tbody) return;
    
    if (!actuals) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No actuals data available. Import CSV statements to view.</td></tr>`;
        return;
    }
    
    const format = formatVal;
    
    const totalObligationsBudget = summary.fixed_spending + summary.discretionary_spending + summary.debt_obligations + summary.savings_contributions;
    const totalObligationsActual = actuals.fixed + actuals.discretionary + actuals.debt_payments + actuals.savings;
    
    const streams = [
        { name: "Income (Inflow)", budget: summary.total_income, actual: actuals.income, type: "income" },
        { name: "Fixed Spending", budget: summary.fixed_spending, actual: actuals.fixed, type: "expense" },
        { name: "Discretionary Spending", budget: summary.discretionary_spending, actual: actuals.discretionary, type: "expense" },
        { name: "Debt Payments", budget: summary.debt_obligations, actual: actuals.debt_payments, type: "expense" },
        { name: "Savings Contributions", budget: summary.savings_contributions, actual: actuals.savings, type: "expense" },
        { name: "Net Remaining Cash Flow", budget: summary.net_remaining_cash_flow, actual: actuals.income - totalObligationsActual, type: "cashflow" }
    ];
    
    let html = "";
    streams.forEach(s => {
        const variance = s.actual - s.budget;
        let statusText = "";
        let statusClass = "";
        let varClass = "";
        
        if (s.type === "income") {
            if (variance > 0) {
                statusText = "Surplus";
                statusClass = "badge-success";
                varClass = "text-emerald";
            } else if (variance < 0) {
                statusText = "Deficit";
                statusClass = "badge-danger";
                varClass = "text-red";
            } else {
                statusText = "On Track";
                statusClass = "badge-neutral";
                varClass = "text-muted";
            }
        } else if (s.type === "expense") {
            if (variance > 0) {
                statusText = "Over Budget";
                statusClass = "badge-danger";
                varClass = "text-red";
            } else if (variance < 0) {
                statusText = "Under Budget";
                statusClass = "badge-success";
                varClass = "text-emerald";
            } else {
                statusText = "On Track";
                statusClass = "badge-neutral";
                varClass = "text-muted";
            }
        } else {
            // Cash flow
            if (variance >= 0) {
                statusText = "Positive Variance";
                statusClass = "badge-success";
                varClass = "text-emerald";
            } else {
                statusText = "Negative Variance";
                statusClass = "badge-danger";
                varClass = "text-red";
            }
        }
        
        const varianceStr = (variance >= 0 ? "+" : "") + format(variance);
        
        const badgeStyle = statusClass === "badge-success" ? "background: rgba(16, 185, 129, 0.15); color: #10b981; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;" :
                           statusClass === "badge-danger" ? "background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;" :
                           "background: rgba(156, 163, 175, 0.15); color: #9ca3af; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;";
                           
        const varStyleColor = varClass === "text-emerald" ? "color: #10b981; font-weight: 500;" : varClass === "text-red" ? "color: #ef4444; font-weight: 500;" : "color: #9ca3af;";
        
        html += `
            <tr>
                <td style="font-weight: 500;">${s.name}</td>
                <td>${format(s.budget)}</td>
                <td>${format(s.actual)}</td>
                <td style="${varStyleColor}">${varianceStr}</td>
                <td><span style="${badgeStyle}">${statusText}</span></td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// ----------------- EDIT MODALS ACTIONS -----------------
function showEditDebtModal(debtId) {
    const debt = currentDebts.find(d => d.id === debtId);
    if (!debt) return;
    
    document.getElementById("edit-debt-id").value = debt.id;
    document.getElementById("edit-debt-account-name").value = debt.account_name;
    document.getElementById("edit-debt-institution").value = debt.institution;
    document.getElementById("edit-debt-type-select").value = debt.debt_type;
    
    adjustEditDebtFormFields(debt.debt_type);
    
    document.getElementById("edit-debt-credit-line").value = debt.total_credit_line || "";
    document.getElementById("edit-debt-balance").value = debt.current_balance;
    document.getElementById("edit-debt-payment").value = debt.monthly_payment;
    document.getElementById("edit-debt-rate").value = debt.interest_rate || "";
    document.getElementById("edit-debt-remaining").value = debt.remaining_payments || "";
    document.getElementById("edit-debt-original").value = debt.original_amount || "";
    document.getElementById("edit-debt-loan-length").value = debt.loan_length_months || "";
    document.getElementById("edit-debt-lender-type").value = debt.lender_type || "N/A";
    
    showModal("edit-debt-modal");
}

function adjustEditDebtFormFields(debtType) {
    const ccField = document.getElementById("edit-field-credit-line");
    const remField = document.getElementById("edit-field-remaining-payments");
    const origField = document.getElementById("edit-field-original-amount");
    const termField = document.getElementById("edit-field-loan-length");
    const lendField = document.getElementById("edit-field-lender-type");

    [ccField, remField, origField, termField, lendField].forEach(el => el.classList.add("hidden"));

    if (debtType === 'Credit Card') {
        ccField.classList.remove("hidden");
    } else if (debtType === 'BNPL') {
        remField.classList.remove("hidden");
        origField.classList.remove("hidden");
    } else if (debtType === 'Car Loan' || debtType === 'Mortgage') {
        termField.classList.remove("hidden");
        origField.classList.remove("hidden");
        remField.classList.remove("hidden");
    } else if (debtType === 'Personal Loan') {
        lendField.classList.remove("hidden");
        origField.classList.remove("hidden");
    }
}

function showEditSavingsModal(savingsId) {
    const savings = currentSavings.find(s => s.id === savingsId);
    if (!savings) return;
    
    document.getElementById("edit-savings-id").value = savings.id;
    document.getElementById("edit-savings-account-name").value = savings.account_name;
    document.getElementById("edit-savings-account-type").value = savings.account_type;
    document.getElementById("edit-savings-balance").value = savings.current_balance;
    document.getElementById("edit-savings-contribution").value = savings.monthly_contribution;
    document.getElementById("edit-savings-yield").value = savings.annual_yield;
    
    showModal("edit-savings-modal");
}

async function handleEditDebtSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const debtId = document.getElementById("edit-debt-id").value;
    const formData = new FormData(form);
    
    const payload = {};
    formData.forEach((value, key) => {
        if (key === "id") return;
        if (value === "") {
            payload[key] = null;
        } else if (!isNaN(value) && key !== "recipient" && key !== "frequency" && key !== "debt_type" && key !== "account_type" && key !== "category" && key !== "institution" && key !== "account_name" && key !== "lender_type") {
            payload[key] = parseFloat(value);
        } else {
            payload[key] = value;
        }
    });

    try {
        const response = await fetch(`/api/debts/${debtId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Submission failed.");
        }
        
        closeModal("edit-debt-modal");
        fetchDashboardData();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function handleEditSavingsSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const savingsId = document.getElementById("edit-savings-id").value;
    const formData = new FormData(form);
    
    const payload = {};
    formData.forEach((value, key) => {
        if (key === "id") return;
        if (value === "") {
            payload[key] = null;
        } else if (!isNaN(value) && key !== "recipient" && key !== "frequency" && key !== "debt_type" && key !== "account_type" && key !== "category" && key !== "account_name") {
            payload[key] = parseFloat(value);
        } else {
            payload[key] = value;
        }
    });

    try {
        const response = await fetch(`/api/savings/${savingsId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Submission failed.");
        }
        
        closeModal("edit-savings-modal");
        fetchDashboardData();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

function scrollToAndEditDebt(debtId) {
    const debtIndex = currentDebts.findIndex(d => d.id === debtId);
    if (debtIndex !== -1) {
        debtCurrentPage = Math.floor(debtIndex / debtRowsPerPage) + 1;
    }
    
    switchTab("debts");
    populateDebtsTab(currentDebts);
    
    setTimeout(() => {
        const row = document.getElementById(`debt-row-${debtId}`);
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            row.classList.add("row-highlight");
            setTimeout(() => {
                row.classList.remove("row-highlight");
            }, 2500);
            showEditDebtModal(debtId);
        }
    }, 150);
}

function renderDebtsPagination(totalItems, totalPages) {
    const container = document.getElementById("debts-pagination");
    if (!container) return;
    
    if (totalItems <= debtRowsPerPage) {
        container.innerHTML = "";
        container.style.display = "none";
        return;
    }
    
    container.style.display = "flex";
    
    const startIndex = (debtCurrentPage - 1) * debtRowsPerPage + 1;
    const endIndex = Math.min(debtCurrentPage * debtRowsPerPage, totalItems);
    
    container.innerHTML = `
        <span class="pagination-info">Showing ${startIndex}-${endIndex} of ${totalItems} accounts</span>
        <div class="pagination-buttons">
            <button class="pagination-btn" id="debt-prev-btn" ${debtCurrentPage === 1 ? 'disabled' : ''} onclick="changeDebtPage(-1)">
                <i class="fa-solid fa-chevron-left"></i> Prev
            </button>
            <button class="pagination-btn" id="debt-next-btn" ${debtCurrentPage === totalPages ? 'disabled' : ''} onclick="changeDebtPage(1)">
                Next <i class="fa-solid fa-chevron-right"></i>
            </button>
        </div>
    `;
}

function changeDebtPage(direction) {
    debtCurrentPage += direction;
    populateDebtsTab(currentDebts);
}

// ----------------- EDIT FIXED & DISCRETIONARY SPENDING -----------------
function showEditFixedModal(id) {
    const item = currentFixed.find(i => i.id === id);
    if (!item) return;
    
    document.getElementById("edit-fixed-id").value = item.id;
    document.getElementById("edit-fixed-category").value = item.category;
    document.getElementById("edit-fixed-subcategory").value = item.subcategory;
    document.getElementById("edit-fixed-monthly-amount").value = item.monthly_amount;
    document.getElementById("edit-fixed-actual-spent").value = item.actual_spent || 0;
    document.getElementById("edit-fixed-link-debt-select").value = item.linked_debt_id || "";
    
    showModal("edit-fixed-modal");
}

function showEditDiscretionaryModal(id) {
    const item = currentDiscretionary.find(i => i.id === id);
    if (!item) return;
    
    document.getElementById("edit-discretionary-id").value = item.id;
    document.getElementById("edit-discretionary-category").value = item.category;
    document.getElementById("edit-discretionary-subcategory").value = item.subcategory;
    document.getElementById("edit-discretionary-monthly-amount").value = item.monthly_amount;
    document.getElementById("edit-discretionary-actual-spent").value = item.actual_spent || 0;
    
    showModal("edit-discretionary-modal");
}

async function handleEditFixedSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const id = formData.get("id");
    
    const payload = {
        category: formData.get("category"),
        subcategory: formData.get("subcategory"),
        monthly_amount: parseFloat(formData.get("monthly_amount")),
        actual_spent: parseFloat(formData.get("actual_spent")) || 0.0,
        linked_debt_id: formData.get("linked_debt_id") ? parseInt(formData.get("linked_debt_id")) : null
    };
    
    try {
        const response = await fetch(`/api/fixed/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error("Failed to update fixed spending.");
        closeModal("edit-fixed-modal");
        fetchDashboardData();
    } catch (err) {
        alert(err.message);
    }
}

async function handleEditDiscretionarySubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const id = formData.get("id");
    
    const payload = {
        category: formData.get("category"),
        subcategory: formData.get("subcategory"),
        monthly_amount: parseFloat(formData.get("monthly_amount")),
        actual_spent: parseFloat(formData.get("actual_spent")) || 0.0
    };
    
    try {
        const response = await fetch(`/api/discretionary/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error("Failed to update discretionary spending.");
        closeModal("edit-discretionary-modal");
        fetchDashboardData();
    } catch (err) {
        alert(err.message);
    }
}

async function handleManualTransactionSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const payload = {
        transaction_date: formData.get("transaction_date"),
        description: formData.get("description"),
        amount: parseFloat(formData.get("amount")),
        category: formData.get("category"),
        account_id: formData.get("account_id") ? parseInt(formData.get("account_id")) : null
    };
    
    try {
        const response = await fetch("/api/transactions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Failed to add manual transaction.");
        }
        form.reset();
        closeModal("add-transaction-modal");
        fetchTransactions();
        fetchDashboardData();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteTransaction(id) {
    if (!confirm("Are you sure you want to delete this transaction?")) return;
    try {
        const response = await fetch(`/api/transactions/${id}`, {
            method: "DELETE"
        });
        if (!response.ok) throw new Error("Failed to delete transaction.");
        fetchTransactions();
        fetchDashboardData();
    } catch (err) {
        alert(err.message);
    }
}
