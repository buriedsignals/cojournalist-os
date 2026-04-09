<script lang="ts">
	import { authStore } from '$lib/stores/auth';
	import { buildApiUrl } from '$lib/config/api';

	interface OrgInfo {
		org_id: string;
		org_name: string;
		balance: number;
		monthly_cap: number;
		seated_count: number;
		tier: string;
	}

	interface Metrics {
		users_by_tier: Record<string, number>;
		total_users: number;
		orgs: OrgInfo[];
		scouts_by_type: Record<string, number>;
		total_scouts: number;
	}

	interface OrgUsage {
		org_id: string;
		org_name: string;
		total_credits: number;
		capped_credits: number;
		revenue: number;
		by_operation: Record<string, number>;
	}

	interface IndividualUsage {
		user_id: string;
		total_credits: number;
		by_operation: Record<string, number>;
	}

	interface MonthlyReport {
		year: number;
		month: number;
		orgs: OrgUsage[];
		individuals: IndividualUsage[];
		total_org_credits: number;
		total_org_capped_credits: number;
		total_org_revenue: number;
		total_individual_credits: number;
		users_by_tier: Record<string, number>;
		active_scouts_by_type: Record<string, number>;
		rate_per_credit: number;
		credit_cap_per_org: number;
	}

	let metrics: Metrics | null = null;
	let report: MonthlyReport | null = null;
	let loading = true;
	let accessDenied = false;
	let error: string | null = null;
	let actionStatus = '';
	let sending = false;

	const now = new Date();
	let selectedMonth = now.getMonth() + 1;
	let selectedYear = now.getFullYear();

	const monthNames = [
		'January', 'February', 'March', 'April', 'May', 'June',
		'July', 'August', 'September', 'October', 'November', 'December'
	];

	async function apiFetch(path: string, opts: RequestInit = {}) {
		const res = await fetch(buildApiUrl(path), {
			credentials: 'include',
			...opts
		});
		if (res.status === 403) {
			throw new Error('ACCESS_DENIED');
		}
		if (!res.ok) {
			const data = await res.json().catch(() => null);
			throw new Error(data?.detail || `HTTP ${res.status}`);
		}
		return res.json();
	}

	async function loadDashboard() {
		loading = true;
		error = null;
		accessDenied = false;
		try {
			const [m, r] = await Promise.all([
				apiFetch('/admin/metrics'),
				apiFetch(`/admin/report/monthly?year=${selectedYear}&month=${selectedMonth}`, { method: 'POST' })
			]);
			metrics = m;
			report = r;
		} catch (e: unknown) {
			if (e instanceof Error && e.message === 'ACCESS_DENIED') {
				accessDenied = true;
			} else {
				error = e instanceof Error ? e.message : 'Failed to load';
			}
		} finally {
			loading = false;
		}
	}

	async function sendEmail() {
		if (!confirm(`Send ${monthNames[selectedMonth - 1]} ${selectedYear} report via email?`)) return;
		sending = true;
		actionStatus = 'Sending...';
		try {
			const data = await apiFetch(
				`/admin/report/send-email?year=${selectedYear}&month=${selectedMonth}`,
				{ method: 'POST' }
			);
			actionStatus = `Sent to ${data.recipients.join(', ')}`;
		} catch (e: unknown) {
			actionStatus = e instanceof Error ? `Failed: ${e.message}` : 'Failed to send';
		} finally {
			sending = false;
		}
	}

	async function downloadJson() {
		if (!report) return;
		const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `report-${selectedYear}-${String(selectedMonth).padStart(2, '0')}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	function handlePeriodChange() {
		actionStatus = '';
		loadDashboard();
	}

	// Load when auth resolves — handles both immediate and async auth init
	$: if ($authStore.user && !metrics && !loading && !error && !accessDenied) {
		loadDashboard();
	}
</script>

<svelte:head>
	<title>Admin - coJournalist</title>
</svelte:head>

{#if !$authStore.user}
	<div class="center">
		<p class="muted">Sign in to access the admin dashboard.</p>
	</div>
{:else if loading}
	<div class="center">
		<p class="muted">Loading dashboard...</p>
	</div>
{:else if accessDenied}
	<div class="center">
		<p class="error">You don't have permission to access the admin dashboard.</p>
	</div>
{:else if error}
	<div class="center">
		<p class="error">{error}</p>
		<button class="btn" on:click={loadDashboard}>Retry</button>
	</div>
{:else if metrics && report}
	<div class="dashboard">
		<header>
			<h1>coJournalist Admin</h1>
			<p class="sub">Revenue dashboard</p>
		</header>

		<!-- KPIs -->
		<div class="kpis">
			<div class="kpi"><b>{metrics.total_users}</b><span>Users</span></div>
			<div class="kpi"><b>{metrics.users_by_tier['free'] ?? 0}</b><span>Free</span></div>
			<div class="kpi"><b>{metrics.users_by_tier['pro'] ?? 0}</b><span>Pro</span></div>
			<div class="kpi"><b>{metrics.users_by_tier['team'] ?? 0}</b><span>Team</span></div>
			<div class="kpi"><b>{metrics.orgs.length}</b><span>Orgs</span></div>
			<div class="kpi"><b>{metrics.total_scouts}</b><span>Scouts</span></div>
		</div>

		<!-- Scouts by type -->
		<h2>Scouts by type</h2>
		<div class="pills">
			{#each Object.entries(metrics.scouts_by_type) as [type, count]}
				<span class="pill">{type}: {count}</span>
			{:else}
				<span class="muted">None</span>
			{/each}
		</div>

		<!-- Period selector -->
		<div class="period-row">
			<h2>Invoice</h2>
			<div class="period-controls">
				<select bind:value={selectedMonth} on:change={handlePeriodChange}>
					{#each monthNames as name, i}
						<option value={i + 1}>{name}</option>
					{/each}
				</select>
				<select bind:value={selectedYear} on:change={handlePeriodChange}>
					{#each Array.from({length: now.getFullYear() - 2023}, (_, i) => now.getFullYear() - i) as year}
						<option value={year}>{year}</option>
					{/each}
				</select>
			</div>
		</div>

		<!-- Invoice table -->
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>Organization</th>
						<th class="r">Credits</th>
						<th class="r">Billable</th>
						<th class="r">Revenue</th>
						<th>Breakdown</th>
					</tr>
				</thead>
				<tbody>
					{#each report.orgs as org}
						<tr>
							<td>{org.org_name || org.org_id.slice(0, 12)}</td>
							<td class="r">{org.total_credits.toLocaleString()}</td>
							<td class="r">{org.capped_credits.toLocaleString()}</td>
							<td class="r">${org.revenue.toFixed(2)}</td>
							<td class="dim">
								{Object.entries(org.by_operation).map(([k, v]) => `${k}: ${v}`).join(', ') || '\u2014'}
							</td>
						</tr>
					{:else}
						<tr><td colspan="5" class="dim">No org usage this month</td></tr>
					{/each}
				</tbody>
				<tfoot>
					<tr>
						<td>Total</td>
						<td class="r">{report.total_org_credits.toLocaleString()}</td>
						<td class="r">{report.total_org_capped_credits.toLocaleString()}</td>
						<td class="r">${report.total_org_revenue.toFixed(2)}</td>
						<td></td>
					</tr>
				</tfoot>
			</table>
		</div>
		<p class="dim" style="margin-top: 4px">
			${report.rate_per_credit}/credit &middot; {report.credit_cap_per_org.toLocaleString()} cap/org/month
		</p>

		<!-- Organizations -->
		{#if metrics.orgs.length > 0}
			<h2>Organizations</h2>
			{#each metrics.orgs as org}
				<div class="card">
					<b>{org.org_name || org.org_id.slice(0, 12)}</b>
					<div class="row">
						<span>Balance</span>
						<span>
							{org.balance.toLocaleString()} / {org.monthly_cap.toLocaleString()}
							({org.monthly_cap ? Math.round(100 * (1 - org.balance / org.monthly_cap)) : 0}% used)
						</span>
					</div>
					<div class="row"><span>Seats</span><span>{org.seated_count}</span></div>
				</div>
			{/each}
		{/if}

		<!-- Actions -->
		<h2>Actions</h2>
		<div class="actions">
			<button class="btn" on:click={sendEmail} disabled={sending}>Email report</button>
			<button class="btn-outline" on:click={downloadJson}>Download JSON</button>
			{#if actionStatus}
				<span class="muted">{actionStatus}</span>
			{/if}
		</div>
	</div>
{/if}

<style>
	.center {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 60vh;
		gap: 12px;
	}
	.dashboard {
		max-width: 920px;
		margin: 0 auto;
		padding: 32px 16px;
	}
	header { margin-bottom: 28px; }
	h1 { font-size: 22px; font-weight: 600; color: #1a1a1a; }
	.sub { color: #888; font-size: 13px; }
	h2 {
		font-size: 13px; font-weight: 600; margin: 24px 0 10px;
		color: #555; text-transform: uppercase; letter-spacing: 0.4px;
	}
	.kpis { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
	.kpi {
		background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
		padding: 14px 18px; flex: 1; min-width: 120px;
	}
	.kpi b { font-size: 26px; display: block; color: #1a1a1a; }
	.kpi span { font-size: 11px; color: #888; }
	.pills { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
	.pill {
		background: #f3f4f6; border-radius: 10px;
		padding: 3px 10px; font-size: 11px; color: #555;
	}
	.period-row {
		display: flex; align-items: center; justify-content: space-between;
		margin: 24px 0 10px; flex-wrap: wrap; gap: 8px;
	}
	.period-row h2 { margin: 0; }
	.period-controls { display: flex; gap: 8px; }
	.period-controls select {
		font-size: 13px; padding: 6px 10px; border-radius: 6px;
		border: 1px solid #d1d5db; background: #fff;
	}
	.table-wrap { overflow-x: auto; }
	table {
		width: 100%; border-collapse: collapse; background: #fff;
		border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;
	}
	th {
		text-align: left; padding: 8px 12px; background: #f9fafb;
		font-size: 11px; font-weight: 600; color: #666;
		text-transform: uppercase; letter-spacing: 0.3px;
		border-bottom: 1px solid #e5e7eb;
	}
	td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
	tr:last-child td { border-bottom: none; }
	.r { text-align: right; font-variant-numeric: tabular-nums; }
	.dim { color: #999; font-size: 11px; }
	tfoot td { font-weight: 600; border-top: 2px solid #e5e7eb; }
	.card {
		background: #fff; border: 1px solid #e5e7eb;
		border-radius: 8px; padding: 14px; margin-bottom: 10px;
	}
	.card b { display: block; margin-bottom: 6px; color: #1a1a1a; }
	.row {
		display: flex; justify-content: space-between;
		font-size: 12px; padding: 2px 0;
	}
	.row span:first-child { color: #888; }
	.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
	.btn {
		font-size: 13px; padding: 7px 14px; border-radius: 6px;
		border: none; background: #1a1a1a; color: #fff;
		font-weight: 500; cursor: pointer;
	}
	.btn:hover { background: #333; }
	.btn-outline {
		font-size: 13px; padding: 7px 14px; border-radius: 6px;
		border: 1px solid #d1d5db; background: #fff; color: #1a1a1a;
		cursor: pointer;
	}
	.btn-outline:hover { background: #f3f4f6; }
	.muted { color: #888; font-size: 13px; }
	.error { color: #dc2626; font-size: 14px; }
</style>
