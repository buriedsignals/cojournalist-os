export type DeploymentKind = 'hosted' | 'supabase';

export interface AgentTargetContext {
	deploymentKind: DeploymentKind;
	appUrl: string;
	apiBaseUrl: string;
	mcpUrl: string;
	skillUrl: string;
	apiKeyCreateUrl: string;
	supabaseAnonKey?: string;
	customMcpUrl?: string;
}

interface ResolveTargetInput {
	deploymentTarget?: string;
	supabaseUrl?: string;
	supabaseAnonKey?: string;
	origin?: string;
	hostname?: string;
	customMcpUrl?: string;
}

const HOSTED_HOSTS = new Set(['cojournalist.ai', 'www.cojournalist.ai', 'cojournalist.onrender.com']);

export const HOSTED_AGENT_TARGET: AgentTargetContext = {
	deploymentKind: 'hosted',
	appUrl: 'https://www.cojournalist.ai',
	apiBaseUrl: 'https://www.cojournalist.ai/functions/v1',
	mcpUrl: 'https://www.cojournalist.ai/mcp',
	skillUrl: 'https://www.cojournalist.ai/skills/cojournalist.md',
	apiKeyCreateUrl: 'https://www.cojournalist.ai'
};

function trimSlash(value: string): string {
	return value.trim().replace(/\/$/, '');
}

export function isHostedCojournalistHost(hostname: string | undefined): boolean {
	return Boolean(hostname && HOSTED_HOSTS.has(hostname));
}

export function getSupabaseProjectRef(supabaseUrl: string | undefined): string | null {
	if (!supabaseUrl) return null;
	try {
		const { hostname } = new URL(trimSlash(supabaseUrl));
		const match = hostname.match(/^([a-z0-9-]+)\.supabase\.co$/i);
		return match?.[1] ?? null;
	} catch {
		return null;
	}
}

export function resolveAgentTargetContext(input: ResolveTargetInput = {}): AgentTargetContext {
	const origin = trimSlash(input.origin || HOSTED_AGENT_TARGET.appUrl);
	const supabaseUrl = trimSlash(input.supabaseUrl || '');
	const isHosted =
		input.deploymentTarget !== 'supabase' || isHostedCojournalistHost(input.hostname);

	if (isHosted || !supabaseUrl) {
		return {
			...HOSTED_AGENT_TARGET,
			appUrl: origin || HOSTED_AGENT_TARGET.appUrl,
			apiKeyCreateUrl: origin || HOSTED_AGENT_TARGET.apiKeyCreateUrl,
			skillUrl: `${origin || HOSTED_AGENT_TARGET.appUrl}/skills/cojournalist.md`
		};
	}

	const customMcpUrl = input.customMcpUrl ? trimSlash(input.customMcpUrl) : '';

	return {
		deploymentKind: 'supabase',
		appUrl: origin,
		apiBaseUrl: `${supabaseUrl}/functions/v1`,
		mcpUrl: customMcpUrl || `${supabaseUrl}/functions/v1/mcp-server`,
		skillUrl: `${origin}/skills/cojournalist.md`,
		apiKeyCreateUrl: origin,
		supabaseAnonKey: input.supabaseAnonKey,
		customMcpUrl: customMcpUrl || undefined
	};
}
