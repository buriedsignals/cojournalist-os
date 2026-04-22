<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { ArrowLeft, Copy, Check, ExternalLink, FileCode, Terminal, Plug, Bot } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth';

	$: backHref = $authStore.authenticated ? '/' : '/login';

	type Section = { id: string; title: string; children?: { id: string; title: string }[] };

	const toc: Section[] = [
		{ id: 'intro', title: 'Introduction' },
		{ id: 'quickstart', title: 'Quickstart' },
		{
			id: 'scouts',
			title: 'Scouts',
			children: [
				{ id: 'scout-page', title: 'Page Scout' },
				{ id: 'scout-location', title: 'Location Scout' },
				{ id: 'scout-beat', title: 'Beat Scout' },
				{ id: 'scout-social', title: 'Social Scout' },
				{ id: 'scout-civic', title: 'Civic Scout' }
			]
		},
		{
			id: 'concepts',
			title: 'Core concepts',
			children: [
				{ id: 'units', title: 'Information units' },
				{ id: 'entities', title: 'Entities' },
				{ id: 'dedup', title: 'Deduplication' },
				{ id: 'verification', title: 'Verification' },
				{ id: 'credits', title: 'Credits' }
			]
		},
		{
			id: 'integrations',
			title: 'Integrations',
			children: [
				{ id: 'mcp', title: 'MCP server' },
				{ id: 'rest', title: 'REST API' },
				{ id: 'cli', title: 'CLI' }
			]
		},
		{
			id: 'cookbook',
			title: 'Cookbook',
			children: [
				{ id: 'recipe-triage', title: 'Daily triage' },
				{ id: 'recipe-extract', title: 'Structured extraction' },
				{ id: 'recipe-export', title: 'Export to CMS' }
			]
		},
		{
			id: 'reference',
			title: 'Reference',
			children: [
				{ id: 'ref-urls', title: 'Base URLs' },
				{ id: 'ref-auth', title: 'Authentication' },
				{ id: 'ref-endpoints', title: 'Endpoints' },
				{ id: 'ref-errors', title: 'Errors' },
				{ id: 'ref-costs', title: 'Credit costs' }
			]
		},
		{ id: 'selfhost', title: 'Self-hosting' },
		{ id: 'help', title: 'Getting help' }
	];

	let activeId = 'intro';
	let observer: IntersectionObserver | null = null;
	let copiedKey: string | null = null;

	function copy(key: string, text: string) {
		navigator.clipboard.writeText(text);
		copiedKey = key;
		setTimeout(() => {
			copiedKey = null;
		}, 1500);
	}

	onMount(() => {
		const ids: string[] = [];
		for (const s of toc) {
			ids.push(s.id);
			if (s.children) for (const c of s.children) ids.push(c.id);
		}
		const elements = ids
			.map((id) => document.getElementById(id))
			.filter((el): el is HTMLElement => el !== null);

		observer = new IntersectionObserver(
			(entries) => {
				const visible = entries
					.filter((e) => e.isIntersecting)
					.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
				if (visible.length > 0) activeId = visible[0].target.id;
			},
			{ rootMargin: '-24px 0px -60% 0px', threshold: [0, 0.25, 1] }
		);
		for (const el of elements) observer.observe(el);
	});

	onDestroy(() => {
		observer?.disconnect();
	});

	const mcpOrigin = typeof window !== 'undefined' ? window.location.origin : 'https://www.cojournalist.ai';
	$: mcpConfig = JSON.stringify(
		{
			mcpServers: {
				cojournalist: {
					url: `${mcpOrigin}/mcp`,
					transport: 'http'
				}
			}
		},
		null,
		2
	);
</script>

<svelte:head>
	<title>Docs — coJournalist</title>
	<meta
		name="description"
		content="Reference for the coJournalist scouts API — MCP, REST, and CLI integrations for connecting your AI agent to monitoring jobs."
	/>
	<link rel="alternate" type="text/plain" title="llms.txt" href="/llms.txt" />
	<link rel="alternate" type="text/plain" title="llms-full.txt" href="/llms-full.txt" />
</svelte:head>

<div class="docs">
	<a href={backHref} class="mobile-back" aria-label="Back">
		<ArrowLeft size={14} />
		<span>Back</span>
	</a>

	<div class="layout">
		<aside class="sidebar" aria-label="Documentation table of contents">
			<div class="sidebar-inner">
				<a href={backHref} class="sidebar-back">
					<ArrowLeft size={13} />
					<span>Back</span>
				</a>
				<div class="sidebar-head">
					<span class="eyebrow">Docs · v2</span>
				</div>
				<ul class="toc">
					{#each toc as section (section.id)}
						<li>
							<a
								href={`#${section.id}`}
								class="toc-link top"
								class:active={activeId === section.id}>{section.title}</a
							>
							{#if section.children}
								<ul class="toc-sub">
									{#each section.children as child (child.id)}
										<li>
											<a
												href={`#${child.id}`}
												class="toc-link"
												class:active={activeId === child.id}>{child.title}</a
											>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ul>
				<div class="sidebar-foot">
					<a href="/swagger">API reference</a>
					<a href="#">Pricing</a>
					<a href="/faq">FAQ</a>
					<a href="https://github.com/buriedsignals/cojournalist-os" target="_blank" rel="noopener noreferrer">
						GitHub
						<ExternalLink size={11} />
					</a>
					<a href="/llms.txt">llms.txt</a>
					<a href="/llms-full.txt">llms-full.txt</a>
				</div>
			</div>
		</aside>

		<main class="content">
			<article>
				<header class="hero">
					<span class="eyebrow">Documentation</span>
					<h1>coJournalist for humans and AI assistants</h1>
					<p class="lede">
						coJournalist is monitoring infrastructure for journalists. It watches websites, local
						news, social profiles, and council agendas on schedules you define, extracts atomic
						facts, de-duplicates across sources, and hands the results to you — or to your AI
						assistant — as a searchable knowledge base.
					</p>
					<div class="pills">
						<a href="#quickstart" class="pill primary">Quickstart</a>
						<a href="#mcp" class="pill">Connect via MCP</a>
						<a href="/swagger" class="pill">API reference</a>
					</div>

					<aside class="callout llms">
						<div class="callout-head">
							<Bot size={14} />
							<strong>For AI assistants</strong>
						</div>
						<p>
							This site follows the
							<a href="https://llmstxt.org" target="_blank" rel="noopener noreferrer">llms.txt</a>
							convention. Machine-readable indexes are available:
						</p>
						<ul>
							<li><a href="/llms.txt"><code>/llms.txt</code></a> — curated link index</li>
							<li><a href="/llms-full.txt"><code>/llms-full.txt</code></a> — full flattened docs</li>
							<li>
								<a href="/swagger"><code>/swagger</code></a> — interactive OpenAPI 3.1 browser; raw
								spec at <code>/functions/v1/openapi-spec</code>
							</li>
							<li><code>/mcp</code> — MCP server endpoint (OAuth 2.1 required)</li>
						</ul>
					</aside>
				</header>

				<!-- INTRODUCTION -->
				<section id="intro">
					<h2>Introduction</h2>
					<p>
						coJournalist turns three tedious parts of reporting into background infrastructure:
						<strong>noticing</strong> that a page changed,
						<strong>understanding</strong> whether the change matters, and
						<strong>remembering</strong> what you already knew. You define a <em>scout</em> — a
						URL, a location, a social handle, a council domain — and coJournalist runs it on a
						schedule, extracts structured information, and drops the results into a knowledge
						graph you own.
					</p>
					<p>
						Everything is addressable by API, so your AI assistant can drive the workflow:
						pull unverified findings, group them by topic, flag dollar amounts and deadlines,
						draft a brief for your morning read. You stay the verifier. Every promotion stamps
						your user ID into an audit trail.
					</p>

					<div class="grid-2">
						<div class="card">
							<h4>Who it's for</h4>
							<ul>
								<li>Local and investigative reporters monitoring beats</li>
								<li>Newsrooms tracking government and civic sources</li>
								<li>Researchers following social accounts and niche publications</li>
								<li>Anyone who wants an AI assistant with editorial guardrails</li>
							</ul>
						</div>
						<div class="card">
							<h4>What makes it different</h4>
							<ul>
								<li>Per-scout change baselines — only real changes fire</li>
								<li>Atomic-fact extraction with vector dedup across sources</li>
								<li>Entity resolution tracked longitudinally</li>
								<li>OAuth-authenticated MCP server plus REST and CLI</li>
							</ul>
						</div>
					</div>
				</section>

				<!-- QUICKSTART -->
				<section id="quickstart">
					<h2>Quickstart</h2>
					<p>Five minutes from zero to a running scout.</p>

					<ol class="steps">
						<li>
							<div class="step-num">1</div>
							<div>
								<h4>Sign in</h4>
								<p>
									Open <a href="https://www.cojournalist.ai" target="_blank" rel="noopener noreferrer"
										>cojournalist.ai</a
									>
									and sign in with your email address.
								</p>
							</div>
						</li>
						<li>
							<div class="step-num">2</div>
							<div>
								<h4>Create your first scout</h4>
								<p>
									Click <strong>+ New scout</strong> in the sidebar. Pick a type (start with Page
									Scout or Location Scout), name it, paste a URL or a location, and schedule it
									(daily / weekly / monthly). The first run establishes a baseline.
								</p>
							</div>
						</li>
						<li>
							<div class="step-num">3</div>
							<div>
								<h4>Connect an AI assistant (optional)</h4>
								<p>
									Click the <strong>Agents</strong> button in the topbar. Pick MCP (for Claude
									Desktop, Cursor, Goose) or API (for ChatGPT Actions, custom agents, scripts).
									Paste the snippet into your client's config.
								</p>
							</div>
						</li>
						<li>
							<div class="step-num">4</div>
							<div>
								<h4>Verify findings</h4>
								<p>
									Open a scout, skim new information units, click <strong>Verify</strong> on the
									ones that matter. Verified units are the ones your assistant can safely cite in
									drafts. Rejected units stay in the audit trail.
								</p>
							</div>
						</li>
					</ol>
				</section>

				<!-- SCOUTS -->
				<section id="scouts">
					<h2>Scouts</h2>
					<p>
						Scouts are the unit of monitoring. Each one has a type (determines the pipeline), a
						schedule (daily/weekly/monthly), and a project it belongs to. Per-run credit costs
						depend on type — see the
						<a href="#ref-costs">credit table</a>.
					</p>

					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Type</th>
									<th>Purpose</th>
									<th>Scope</th>
									<th>Cost / run</th>
								</tr>
							</thead>
							<tbody>
								<tr>
									<td><a href="#scout-page"><code>web</code> — Page Scout</a></td>
									<td>Watches a single URL for content changes</td>
									<td>URL + optional topic filter</td>
									<td>1 credit</td>
								</tr>
								<tr>
									<td><a href="#scout-location"><code>pulse</code> — Location Scout</a></td>
									<td>Local news for a geography, favouring niche sources</td>
									<td>Location + optional criteria</td>
									<td>7 credits</td>
								</tr>
								<tr>
									<td><a href="#scout-beat"><code>pulse</code> — Beat Scout</a></td>
									<td>Topic news across reliable outlets</td>
									<td>Criteria (no location required)</td>
									<td>7 credits</td>
								</tr>
								<tr>
									<td><a href="#scout-social"><code>social</code> — Social Scout</a></td>
									<td>Monitors a social profile for new/removed posts</td>
									<td>Platform + handle</td>
									<td>2–15 credits</td>
								</tr>
								<tr>
									<td><a href="#scout-civic"><code>civic</code> — Civic Scout</a></td>
									<td>Council agendas + promise extraction from PDFs</td>
									<td>Council domain</td>
									<td>20 credits</td>
								</tr>
							</tbody>
						</table>
					</div>

					<h3 id="scout-page">Page Scout</h3>
					<p>
						Point it at any URL. Uses Firecrawl <code>changeTracking</code> with a per-scout tag so
						each scout has its own baseline — you can track ten variants of the same page without
						interference. Only real content changes fire notifications. Optional topic filter lets
						AI skip changes that don't match your criteria. First-run behaviour is controlled by
						the "Import current page data" toggle: off (default) establishes baseline only; on
						extracts the current content into your knowledge base as the first unit.
					</p>

					<h3 id="scout-location">Location Scout</h3>
					<p>
						Give it a place (city, neighbourhood, district). Location Scout generates
						location-aware search queries in your preferred language (12 locales), favours niche
						sources (local blogs, community publishers, regional sites) over national outlets, and
						returns atomic facts that passed similarity dedup against your prior runs.
					</p>

					<h3 id="scout-beat">Beat Scout</h3>
					<p>
						Same underlying <code>pulse</code> pipeline as Location Scout, but sourced from
						established outlets (reliable mode) and criteria-driven rather than location-driven.
						Use it to watch a topic across geographies — <em>housing supply decisions</em>,
						<em>state AG activity</em>, <em>FCC filings</em> — where the where doesn't matter.
					</p>

					<h3 id="scout-social">Social Scout</h3>
					<p>
						Monitors Instagram, X, Facebook, LinkedIn, TikTok profiles via Apify. Captures new
						posts and — importantly — <strong>deletions</strong> (useful for politicians and PR
						firms). Image-aware criteria: your filter can match on caption text, alt text, or
						image content. Facebook is more expensive because Meta makes it hard.
					</p>

					<h3 id="scout-civic">Civic Scout</h3>
					<p>
						Give it a council domain. Civic Scout discovers meeting pages, downloads agendas and
						minutes (often PDFs), has Gemini extract <strong>promises</strong> — commitments,
						deadlines, and dollar figures — with meeting-date context. Costs more because PDF
						parsing and promise extraction are expensive.
					</p>
				</section>

				<!-- CONCEPTS -->
				<section id="concepts">
					<h2>Core concepts</h2>

					<h3 id="units">Information units</h3>
					<p>
						A unit is an atomic fact extracted from one or more sources. "Council approved $2.3M
						for SRP road paving with a Q4 2026 target" is one unit. Six articles reporting that
						decision become one unit with six <code>source_url</code>s. Units carry fields for the
						event date (<code>occurred_at</code>), when the scout found it (<code>extracted_at</code>),
						who verified it (<code>verified_by</code>), and free-form tags. Units are embedded
						with Gemini multimodal embeddings and stored in pgvector for semantic search.
					</p>

					<h3 id="entities">Entities</h3>
					<p>
						People, organisations, locations, and documents are resolved into
						<strong>entities</strong> across units. "Salt River Pima Community" mentioned in four
						units resolves to one entity your assistant can follow over time. Entities have their
						own knowledge page and cross-link to every unit that mentions them.
					</p>

					<h3 id="dedup">Deduplication</h3>
					<p>Dedup operates at four layers, so nothing gets surfaced twice:</p>
					<ul>
						<li>
							<strong>Fact-level</strong> — semantic similarity on extracted facts. Six rewrites of
							the same wire story become one unit.
						</li>
						<li>
							<strong>Source-level</strong> — each unit stores every source URL, so your assistant
							can cite the original and the follow-ups.
						</li>
						<li>
							<strong>Entity-level</strong> — entity resolution means "SRP", "Salt River Project",
							and "Salt River Pima" don't fracture into three histories.
						</li>
						<li>
							<strong>Time-level</strong> — queries can filter by <code>occurred_at</code> (when
							the event happened) or <code>extracted_at</code> (when we found it).
						</li>
					</ul>

					<h3 id="verification">Verification</h3>
					<p>
						Units land in an <em>unverified</em> state. An editor (you) reviews and calls
						<code>promoteUnit</code> or <code>rejectUnit</code>. Every verification stamps your
						user ID into <code>verified_by</code> with a timestamp, so an editor can later audit
						who cleared what. AI assistants can draft using any unit but by convention only cite
						verified ones — the verification state is exposed on every API response so agents can
						be configured to hold the line.
					</p>

					<h3 id="credits">Credits</h3>
					<p>
						Credits are the unit of cost. Every scout run decrements the credit balance on the
						project (individual users) or organisation (team plans). Free tier: 100/month. Pro:
						1,000/month. Team: 5,000/month shared. See
						<a href="#">pricing</a> and the <a href="#ref-costs">cost table</a>.
					</p>
				</section>

				<!-- INTEGRATIONS -->
				<section id="integrations">
					<h2>Integrations</h2>
					<p>
						Three surfaces; pick the one that matches your client. Most journalists end up using
						all three at different points.
					</p>

					<div class="surface-grid">
						<a href="#mcp" class="surface">
							<div class="surface-icon"><Plug size={18} /></div>
							<h4>MCP</h4>
							<p>For Claude Desktop, Cursor, Windsurf, Goose, any MCP client.</p>
						</a>
						<a href="#rest" class="surface">
							<div class="surface-icon"><FileCode size={18} /></div>
							<h4>REST API</h4>
							<p>For ChatGPT Actions, custom agents, browser automations, scripts.</p>
						</a>
						<a href="#cli" class="surface">
							<div class="surface-icon"><Terminal size={18} /></div>
							<h4>CLI (<code>cojo</code>)</h4>
							<p>Deno-based binary for terminal workflows and shell automation.</p>
						</a>
					</div>

					<h3 id="mcp">MCP server</h3>
					<p>
						coJournalist ships an embedded MCP server with its own OAuth 2.1 authorization server
						(RFC 8414 metadata + RFC 7591 dynamic registration). Your MCP client handles the full
						OAuth dance — you never paste tokens. The endpoint is:
					</p>

					<div class="code-block">
						<button
							class="copy-btn"
							on:click={() => copy('mcp-url', `${mcpOrigin}/mcp`)}
							aria-label="Copy MCP URL"
						>
							{#if copiedKey === 'mcp-url'}<Check size={12} /> Copied{:else}<Copy size={12} /> Copy{/if}
						</button>
<pre><code>{mcpOrigin}/mcp</code></pre>
					</div>

					<p>Drop this into your MCP client config (example: <code>claude_desktop_config.json</code>):</p>

					<div class="code-block">
						<button
							class="copy-btn"
							on:click={() => copy('mcp-config', mcpConfig)}
							aria-label="Copy MCP config"
						>
							{#if copiedKey === 'mcp-config'}<Check size={12} /> Copied{:else}<Copy size={12} /> Copy{/if}
						</button>
						<pre><code>{mcpConfig}</code></pre>
					</div>

					<p>Tools exposed over MCP (non-exhaustive):</p>
					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Tool</th>
									<th>Does</th>
								</tr>
							</thead>
							<tbody>
								<tr><td><code>list_scouts</code></td><td>List scouts in the current project</td></tr>
								<tr><td><code>get_scout</code></td><td>Fetch a scout by ID with latest run status</td></tr>
								<tr><td><code>run_scout</code></td><td>Trigger an on-demand run (counts against credits)</td></tr>
								<tr><td><code>list_units</code></td><td>List information units, filterable by scout / verified / time</td></tr>
								<tr><td><code>search_units</code></td><td>Semantic search across units</td></tr>
								<tr><td><code>promote_unit</code> / <code>reject_unit</code></td><td>Verification actions; stamps your user ID</td></tr>
								<tr><td><code>list_entities</code></td><td>People, orgs, locations, documents</td></tr>
								<tr><td><code>ingest_url</code></td><td>Ingest an ad-hoc URL into the knowledge base</td></tr>
								<tr><td><code>export_project</code></td><td>Export a project as markdown or JSON</td></tr>
							</tbody>
						</table>
					</div>

					<h3 id="rest">REST API</h3>
					<p>
						Base URL: <code>https://www.cojournalist.ai/functions/v1</code>. Auth via a
						<code>cj_…</code> API key (create one in the in-app <strong>Agents → API</strong> modal) sent
						as <code>Authorization: Bearer cj_…</code>. Full OpenAPI 3.1 spec at
						<a href="/swagger">/swagger</a>; raw JSON at <code>/functions/v1/openapi-spec</code>.
					</p>

					<div class="code-block">
						<button
							class="copy-btn"
							on:click={() =>
								copy(
									'rest-example',
									`curl https://www.cojournalist.ai/functions/v1/scouts \\
  -H "Authorization: Bearer $COJO_TOKEN"

curl "https://www.cojournalist.ai/functions/v1/units?verified=false&limit=20" \\
  -H "Authorization: Bearer $COJO_TOKEN"`
								)}
							aria-label="Copy curl example"
						>
							{#if copiedKey === 'rest-example'}<Check size={12} /> Copied{:else}<Copy size={12} /> Copy{/if}
						</button>
<pre><code>{`curl https://www.cojournalist.ai/functions/v1/scouts \\
  -H "Authorization: Bearer $COJO_TOKEN"

curl "https://www.cojournalist.ai/functions/v1/units?verified=false&limit=20" \\
  -H "Authorization: Bearer $COJO_TOKEN"`}</code></pre>
					</div>

					<p>
						Responses are JSON. Lists return a paginated envelope:
						<code>{`{ "items": [...], "pagination": { "total", "offset", "limit", "has_more" } }`}</code>.
						Errors return <code>{`{ "error": "…", "code": "…" }`}</code>.
					</p>

					<h3 id="cli">CLI</h3>
					<p>
						<code>cojo</code> is a tiny Deno-based binary that speaks the same REST API. Useful for
						shell pipelines, nightly scripts, and piping Markdown exports into your clipboard or
						static site generator.
					</p>

					<div class="code-block">
						<button
							class="copy-btn"
							on:click={() =>
								copy(
									'cli-install',
									`curl -L https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mac \\
  -o /usr/local/bin/cojo
chmod +x /usr/local/bin/cojo
cojo config set api_url=https://www.cojournalist.ai/api
cojo config set auth_token=<cj_... API key>
cojo scouts list`
								)}
							aria-label="Copy CLI install"
						>
							{#if copiedKey === 'cli-install'}<Check size={12} /> Copied{:else}<Copy size={12} /> Copy{/if}
						</button>
<pre><code>{`# Install (macOS)
curl -L https://github.com/buriedsignals/cojournalist-os/releases/latest/download/cojo-mac \\
  -o /usr/local/bin/cojo
chmod +x /usr/local/bin/cojo

# Configure (generate a cj_... API key in the app: Agents → API → Create key)
cojo config set api_url=https://www.cojournalist.ai/api
cojo config set auth_token=<cj_... API key>

# Use
cojo scouts list
cojo units list --since 7d --verified
cojo units verify <id> --notes "Cross-checked with minutes"
cojo export claude --project <id> --limit 50 | pbcopy`}</code></pre>
					</div>
				</section>

				<!-- COOKBOOK -->
				<section id="cookbook">
					<h2>Cookbook</h2>
					<p>Worked examples. Copy, adapt, ship.</p>

					<h3 id="recipe-triage">Daily triage with an AI assistant</h3>
					<div class="recipe">
						<div class="recipe-block">
							<div class="recipe-label">You → Claude Desktop</div>
							<p class="recipe-prompt">
								Pull all unverified units from my Phoenix Council and Oakland local scouts this
								week. Group by topic, flag anything mentioning dollar amounts or deadlines, and
								draft a 150-word brief I can read over coffee.
							</p>
						</div>
						<div class="recipe-block">
							<div class="recipe-label">Claude Desktop</div>
							<ol class="recipe-steps">
								<li>Calls <code>list_scouts()</code> → finds Phoenix Council and Oakland local.</li>
								<li>
									Calls <code>list_units(scout_ids=[…], verified=false, since='7d')</code> → 9 units.
								</li>
								<li>
									Calls <code>search_units(query='$M OR deadline OR by 2026')</code> → narrows to 4.
								</li>
								<li>Drafts a 150-word brief with source links.</li>
								<li>Waits for your <code>promote_unit</code> / <code>reject_unit</code> calls.</li>
							</ol>
						</div>
						<p class="recipe-note">
							The assistant never publishes on its own. <code>promote_unit</code> is the editorial
							checkpoint — it stamps your user ID into the audit trail.
						</p>
					</div>

					<h3 id="recipe-extract">Structured extraction</h3>
					<div class="recipe">
						<div class="recipe-block">
							<div class="recipe-label">You → ChatGPT (REST Action)</div>
							<p class="recipe-prompt">
								Pull the last 30 agenda items from my cityof-oakland civic scout. For each, return
								title, meeting date, and a one-line summary. Give it to me as a markdown table I
								can paste into our CMS.
							</p>
						</div>
						<p>
							Behind the scenes: <code>GET /units?scout_id=…&amp;limit=30</code> →
							<code>/units/search</code> narrows to agenda-relevant ones → assistant renders the
							table. All on-the-fly, no storage on your machine.
						</p>
					</div>

					<h3 id="recipe-export">Export to CMS</h3>
					<div class="recipe">
<pre><code>{`# Export a project as Claude-flavoured Markdown and pipe into your CMS
cojo export claude --project phoenix-council --limit 50 \\
  | pandoc -f markdown -t html \\
  | curl -X POST https://cms.example.com/api/drafts \\
      -H "Authorization: Bearer $CMS_TOKEN" \\
      -H "Content-Type: text/html" --data-binary @-`}</code></pre>
						<p class="recipe-note">
							Swap <code>--format claude</code> for <code>json</code> or
							<code>markdown</code> depending on downstream needs.
						</p>
					</div>
				</section>

				<!-- REFERENCE -->
				<section id="reference">
					<h2>Reference</h2>

					<h3 id="ref-urls">Base URLs</h3>
					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Surface</th>
									<th>URL</th>
								</tr>
							</thead>
							<tbody>
								<tr><td>App</td><td><code>https://www.cojournalist.ai</code></td></tr>
								<tr><td>REST API</td><td><code>https://www.cojournalist.ai/functions/v1</code></td></tr>
								<tr><td>MCP server</td><td><code>https://www.cojournalist.ai/mcp</code></td></tr>
								<tr><td>OpenAPI spec</td><td><code>/functions/v1/openapi-spec</code> (JSON)</td></tr>
								<tr><td>Swagger UI</td><td><a href="/swagger">/swagger</a></td></tr>
								<tr><td>llms.txt</td><td><a href="/llms.txt">/llms.txt</a></td></tr>
								<tr><td>llms-full.txt</td><td><a href="/llms-full.txt">/llms-full.txt</a></td></tr>
							</tbody>
						</table>
					</div>

					<h3 id="ref-auth">Authentication</h3>
					<p>
						<strong>REST / CLI</strong>: <code>cj_…</code> API key in the <code>Authorization: Bearer</code>
						header. Generate keys from <strong>Agents → API</strong> in the app — they are scoped to
						your account and revocable from the same modal. <strong>MCP</strong>: OAuth via the
						connector; no manual token handling.
					</p>
					<p>
						<strong>MCP</strong>: full OAuth 2.1 with PKCE, RFC 8414 metadata, and RFC 7591 dynamic
						client registration. Your MCP client handles the flow — you only paste the URL.
					</p>

					<h3 id="ref-endpoints">Endpoints (summary)</h3>
					<p>Full spec at <a href="/swagger">/swagger</a>. Highlights:</p>
					<div class="table-wrap">
						<table>
							<thead>
								<tr><th>Method</th><th>Path</th><th>What</th></tr>
							</thead>
							<tbody>
								<tr><td>GET</td><td><code>/projects</code></td><td>List projects</td></tr>
								<tr><td>POST</td><td><code>/projects</code></td><td>Create a project</td></tr>
								<tr><td>GET</td><td><code>/scouts</code></td><td>List scouts</td></tr>
								<tr><td>POST</td><td><code>/scouts</code></td><td>Create a scout</td></tr>
								<tr><td>POST</td><td><code>/execute-scout</code></td><td>Trigger a scout run</td></tr>
								<tr><td>GET</td><td><code>/units</code></td><td>List information units</td></tr>
								<tr><td>POST</td><td><code>/units/search</code></td><td>Semantic search</td></tr>
								<tr><td>POST</td><td><code>/units/:id/verify</code></td><td>Promote a unit</td></tr>
								<tr><td>GET</td><td><code>/entities</code></td><td>List resolved entities</td></tr>
								<tr><td>POST</td><td><code>/ingest</code></td><td>Ingest a URL or raw text</td></tr>
								<tr><td>POST</td><td><code>/export-claude</code></td><td>Export project as Claude-flavoured Markdown</td></tr>
							</tbody>
						</table>
					</div>

					<h3 id="ref-errors">Errors</h3>
					<p>Every error response uses the same shape:</p>
<pre><code>{`{
  "error": "human-readable message",
  "code": "machine_code"
}`}</code></pre>
					<p>Common codes:</p>
					<ul>
						<li><code>unauthorized</code> — missing or expired token</li>
						<li><code>forbidden</code> — token valid, resource not yours</li>
						<li><code>not_found</code> — no such resource</li>
						<li><code>insufficient_credits</code> — run would exceed your plan</li>
						<li><code>rate_limited</code> — too many requests; retry with exponential backoff</li>
						<li><code>validation_error</code> — request body failed schema validation</li>
					</ul>

					<h3 id="ref-costs">Credit costs</h3>
					<div class="table-wrap">
						<table>
							<thead>
								<tr><th>Action</th><th>Credits</th></tr>
							</thead>
							<tbody>
								<tr><td>Page Scout run (<code>web</code>)</td><td>1</td></tr>
								<tr><td>Location / Beat Scout run (<code>pulse</code>)</td><td>7</td></tr>
								<tr><td>Social Scout — Instagram / X / TikTok</td><td>2</td></tr>
								<tr><td>Social Scout — Facebook</td><td>15</td></tr>
								<tr><td>Civic Scout run (weekly or monthly only)</td><td>10 <small>(refunded when a run queues 0 docs)</small></td></tr>
								<tr><td>Ad-hoc data extraction</td><td>varies by channel</td></tr>
							</tbody>
						</table>
					</div>
					<p>
						Monthly budget = (cost per run) × (runs per month). A daily Page Scout = 30 credits/mo;
						a weekly Civic Scout = up to 40 credits/mo (less when a week passes with no new council documents — those runs refund the 10 credits automatically). Plan math lives on the <a href="#">pricing page</a>.
					</p>
				</section>

				<!-- SELF-HOSTING -->
				<section id="selfhost">
					<h2>Self-hosting</h2>
					<p>
						coJournalist is source-available under the
						<a href="/faq">Sustainable Use License</a> — use it for your newsroom freely, don't
						resell it as a service. Self-hosted deployments run on your own Supabase project with
						your Firecrawl, Gemini, Apify, and Resend keys. Same feature set as SaaS. No telemetry.
					</p>
					<p>
						The <a href="https://github.com/buriedsignals/cojournalist-os" target="_blank" rel="noopener noreferrer"
							>GitHub repo</a
						>
						has an automated setup flow — drop your AI coding agent into the repo, run the
						<code>setup</code> skill, and it provisions everything from a fresh Supabase project
						to the Edge Functions and the frontend.
					</p>
				</section>

				<!-- HELP -->
				<section id="help">
					<h2>Getting help</h2>
					<ul class="flat-list">
						<li><a href="/faq">FAQ</a> — licensing, self-hosting, editorial workflow</li>
						<li><a href="#">Pricing</a> — plans, credits, team seats</li>
						<li>
							<a href="https://github.com/buriedsignals/cojournalist-os/issues" target="_blank" rel="noopener noreferrer"
								>Open an issue</a
							>
							— bugs and feature requests
						</li>
						<li>
							In-app <strong>Feedback</strong> button — routes to Linear, a human reads it
						</li>
						<li>
							<a href="https://github.com/buriedsignals/cojournalist-os/discussions" target="_blank" rel="noopener">GitHub discussions</a>
							— for questions and help from the community
						</li>
					</ul>
				</section>

				<footer class="foot">
					<a href={backHref} class="foot-link">← Back to coJournalist</a>
					<a
						href="https://github.com/buriedsignals/cojournalist-os"
						target="_blank"
						rel="noopener noreferrer"
						class="foot-link"
					>
						GitHub <ExternalLink size={12} />
					</a>
				</footer>
			</article>
		</main>
	</div>
</div>

<style>
	.docs {
		min-height: 100vh;
		background: var(--color-bg);
		font-family: 'DM Sans', -apple-system, system-ui, sans-serif;
		color: var(--color-ink);
	}

	.mobile-back {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 1rem 1.5rem 0.25rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-ink-muted);
		text-decoration: none;
		transition: color 0.15s ease;
	}
	.mobile-back:hover { color: var(--color-primary-deep); }
	@media (min-width: 960px) { .mobile-back { display: none; } }

	.sidebar-back {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		margin-bottom: 1.5rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-ink-subtle);
		text-decoration: none;
		transition: color 0.15s ease;
	}
	.sidebar-back:hover { color: var(--color-primary-deep); }

	.layout {
		display: grid;
		grid-template-columns: 1fr;
		max-width: 1200px;
		margin: 0 auto;
		padding: 0 1.5rem;
	}

	@media (min-width: 960px) {
		.layout {
			grid-template-columns: 220px 1fr;
			gap: 3rem;
		}
	}

	.sidebar { display: none; }
	@media (min-width: 960px) { .sidebar { display: block; } }

	.sidebar-inner {
		position: sticky;
		top: 0;
		padding: 3rem 0;
		max-height: 100vh;
		overflow-y: auto;
	}

	.sidebar-head {
		margin-bottom: 1rem;
	}

	.eyebrow {
		display: inline-block;
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.15em;
		text-transform: uppercase;
		color: var(--color-primary-deep);
	}

	.toc, .toc-sub {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.toc > li { margin-bottom: 0.125rem; }
	.toc-sub {
		margin: 0.25rem 0 0.5rem 0;
		padding-left: 0.75rem;
		border-left: 1px solid rgba(0, 0, 0, 0.06);
	}
	.toc-link {
		display: block;
		padding: 0.3125rem 0.5rem;
		font-size: 0.8125rem;
		color: var(--color-ink-muted);
		text-decoration: none;
		border-radius: 0.375rem;
		line-height: 1.4;
		transition: background 0.12s ease, color 0.12s ease;
	}
	.toc-link.top { font-weight: 600; color: var(--color-ink); }
	.toc-link:hover { background: rgba(78, 44, 120, 0.06); color: var(--color-primary-deep); }
	.toc-link.active { color: var(--color-primary-deep); background: rgba(78, 44, 120, 0.1); }

	.sidebar-foot {
		margin-top: 1.25rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.sidebar-foot a {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: var(--color-ink-muted);
		text-decoration: none;
	}
	.sidebar-foot a:hover { color: var(--color-primary-deep); }

	.content { padding: 3rem 0 6rem; min-width: 0; }
	article { max-width: 760px; }

	.hero { margin-bottom: 4rem; }

	.hero h1 {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: clamp(2rem, 4vw, 2.75rem);
		font-weight: 600;
		line-height: 1.2;
		color: var(--color-ink);
		margin: 0.875rem 0 1rem 0;
		letter-spacing: -0.015em;
	}

	.lede {
		font-size: 1.0625rem;
		line-height: 1.7;
		color: var(--color-ink-muted);
		margin: 0;
		max-width: 640px;
	}

	.pills {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 1.5rem;
	}
	.pill {
		display: inline-flex;
		align-items: center;
		padding: 0.4375rem 0.875rem;
		border-radius: 999px;
		border: 1px solid rgba(0, 0, 0, 0.08);
		background: white;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-ink);
		text-decoration: none;
		transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
	}
	.pill:hover { border-color: rgba(78, 44, 120, 0.4); color: var(--color-primary-deep); }
	.pill.primary {
		background: var(--color-ink);
		color: var(--color-bg);
		border-color: var(--color-ink);
	}
	.pill.primary:hover {
		background: var(--color-ink);
		color: white;
	}

	.callout {
		margin-top: 2rem;
		padding: 1rem 1.125rem;
		background: rgba(107, 63, 160, 0.06);
		border: 1px solid rgba(107, 63, 160, 0.2);
		border-radius: 0.75rem;
	}
	.callout.llms ul {
		margin: 0.5rem 0 0 0;
		padding-left: 1.125rem;
		font-size: 0.8125rem;
		line-height: 1.8;
		color: var(--color-ink-muted);
	}
	.callout.llms p {
		margin: 0;
		font-size: 0.8125rem;
		line-height: 1.6;
		color: var(--color-ink-muted);
	}
	.callout-head {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--color-primary-deep);
		letter-spacing: 0.02em;
		text-transform: uppercase;
		margin-bottom: 0.375rem;
	}

	section { margin-top: 4rem; scroll-margin-top: 2rem; }

	section h2 {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.875rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 1rem 0;
		letter-spacing: -0.015em;
	}

	section h3 {
		font-family: 'DM Sans', sans-serif;
		font-size: 1.0625rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 2rem 0 0.75rem 0;
		letter-spacing: -0.005em;
		scroll-margin-top: 2rem;
	}

	h4 {
		font-family: 'DM Sans', sans-serif;
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-ink);
		margin: 0 0 0.5rem 0;
	}

	section p, .content p {
		font-size: 0.9375rem;
		line-height: 1.7;
		color: var(--color-ink-muted);
		margin: 0 0 1rem 0;
	}
	section p:last-child { margin-bottom: 0; }

	section ul, .content ul {
		margin: 0 0 1rem 0;
		padding-left: 1.25rem;
		font-size: 0.9375rem;
		line-height: 1.7;
		color: var(--color-ink-muted);
	}
	section ul li { margin-bottom: 0.375rem; }
	section ul strong { color: var(--color-ink); font-weight: 600; }

	a {
		color: var(--color-primary-deep);
		text-decoration: none;
		font-weight: 500;
	}
	a:hover { text-decoration: underline; }

	code {
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8125em;
		padding: 0.0625rem 0.375rem;
		background: rgba(107, 63, 160, 0.08);
		color: var(--color-primary);
		border-radius: 0.25rem;
		font-weight: 500;
	}

	pre {
		position: relative;
		margin: 0.75rem 0 1rem 0;
		padding: 1rem 1.125rem;
		background: var(--color-ink);
		color: var(--color-surface);
		border-radius: 0.625rem;
		font-size: 0.75rem;
		line-height: 1.6;
		overflow-x: auto;
	}
	pre code {
		background: transparent;
		color: inherit;
		padding: 0;
		font-weight: 400;
	}

	.code-block {
		position: relative;
	}
	.code-block pre { padding-right: 4.75rem; }
	.copy-btn {
		position: absolute;
		top: 0.625rem;
		right: 0.625rem;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		font-family: inherit;
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--color-border-strong);
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 0.375rem;
		cursor: pointer;
		transition: background 0.15s ease, color 0.15s ease;
		z-index: 1;
	}
	.copy-btn:hover {
		background: rgba(255, 255, 255, 0.14);
		color: white;
	}

	.grid-2 {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.875rem;
		margin: 1.25rem 0 0 0;
	}
	@media (min-width: 720px) {
		.grid-2 { grid-template-columns: 1fr 1fr; }
	}

	.card {
		padding: 1.125rem 1.25rem;
		background: white;
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.875rem;
	}
	.card h4 { margin-bottom: 0.625rem; }
	.card ul {
		margin: 0;
		padding-left: 1.125rem;
		font-size: 0.8125rem;
		line-height: 1.6;
	}
	.card ul li { margin-bottom: 0.25rem; }

	.steps {
		list-style: none;
		margin: 1.25rem 0 0 0;
		padding: 0;
		counter-reset: step;
	}
	.steps > li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.875rem;
		padding: 1rem 0;
		border-bottom: 1px solid rgba(0, 0, 0, 0.06);
	}
	.steps > li:last-child { border-bottom: none; }
	.step-num {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 999px;
		background: rgba(107, 63, 160, 0.12);
		color: var(--color-primary-deep);
		font-size: 0.75rem;
		font-weight: 700;
	}
	.steps h4 { margin-top: 0.125rem; }
	.steps p { margin-top: 0.25rem; font-size: 0.875rem; }

	.table-wrap {
		margin: 0.75rem 0 1.25rem 0;
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.75rem;
		overflow: hidden;
		background: white;
	}
	.table-wrap table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8125rem;
	}
	.table-wrap th, .table-wrap td {
		text-align: left;
		padding: 0.625rem 0.875rem;
		border-bottom: 1px solid rgba(0, 0, 0, 0.05);
		vertical-align: top;
	}
	.table-wrap thead {
		background: rgba(0, 0, 0, 0.02);
		font-weight: 600;
		color: var(--color-ink);
	}
	.table-wrap tr:last-child td { border-bottom: none; }

	.surface-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
		margin: 1.25rem 0 0 0;
	}
	@media (min-width: 720px) {
		.surface-grid { grid-template-columns: repeat(3, 1fr); }
	}
	.surface {
		display: block;
		padding: 1rem 1.125rem;
		background: white;
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.75rem;
		text-decoration: none;
		color: var(--color-ink);
		transition: border-color 0.15s ease, transform 0.15s ease;
	}
	.surface:hover {
		border-color: rgba(78, 44, 120, 0.35);
		transform: translateY(-1px);
	}
	.surface-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border-radius: 0.5rem;
		background: rgba(107, 63, 160, 0.1);
		color: var(--color-primary-deep);
		margin-bottom: 0.5rem;
	}
	.surface h4 { margin: 0 0 0.25rem 0; }
	.surface p {
		margin: 0;
		font-size: 0.8125rem;
		line-height: 1.5;
		color: var(--color-ink-muted);
	}

	.recipe {
		margin: 0.75rem 0 1.5rem 0;
		padding: 1.125rem 1.25rem;
		background: white;
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.875rem;
	}
	.recipe-block {
		margin-bottom: 0.875rem;
	}
	.recipe-label {
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-primary-deep);
		margin-bottom: 0.375rem;
	}
	.recipe-prompt {
		padding: 0.75rem 0.875rem;
		background: rgba(107, 63, 160, 0.06);
		border-left: 3px solid var(--color-primary);
		border-radius: 0.375rem;
		font-size: 0.875rem;
		line-height: 1.6;
		margin: 0;
		color: var(--color-ink);
	}
	.recipe-steps {
		margin: 0.5rem 0 0 0;
		padding-left: 1.125rem;
		font-size: 0.8125rem;
		line-height: 1.65;
		color: var(--color-ink-muted);
	}
	.recipe-steps li { margin-bottom: 0.25rem; }
	.recipe-note {
		margin-top: 0.875rem;
		padding-top: 0.875rem;
		border-top: 1px dashed rgba(0, 0, 0, 0.1);
		font-size: 0.8125rem;
		color: var(--color-ink-muted);
	}

	.flat-list {
		list-style: none;
		padding-left: 0;
	}
	.flat-list li {
		padding: 0.375rem 0;
		border-bottom: 1px dashed rgba(0, 0, 0, 0.06);
	}
	.flat-list li:last-child { border-bottom: none; }

	.foot {
		margin-top: 5rem;
		padding-top: 2rem;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.foot-link {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-ink-muted);
	}
	.foot-link:hover { color: var(--color-primary-deep); }
</style>
