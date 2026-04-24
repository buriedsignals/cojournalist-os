export interface BeatLocationShape {
  city: string | null;
  country: string | null;
  countryCode: string | null;
}

const COUNTRY_ALIAS_MAP: Record<string, string[]> = {
  GB: ["united kingdom", "uk", "britain", "british", "england", "scotland", "wales", "northern ireland", "gov.uk"],
  US: ["united states", "us", "usa", "american", ".gov"],
  CA: ["canada", "canadian", ".gc.ca"],
  AU: ["australia", "australian", ".gov.au"],
  NZ: ["new zealand", "nz", ".govt.nz"],
  IE: ["ireland", "irish", ".gov.ie"],
  FR: ["france", "french", ".gouv.fr"],
  DE: ["germany", "german", ".de"],
  CH: ["switzerland", "swiss", ".ch"],
};

export function parseBeatLocation(v: unknown): BeatLocationShape {
  if (!v) return { city: null, country: null, countryCode: null };
  if (typeof v === "string") {
    const parts = v.split(",").map((s) => s.trim());
    return {
      city: parts[0] || null,
      country: parts[1] || null,
      countryCode: null,
    };
  }
  if (typeof v !== "object") {
    return { city: null, country: null, countryCode: null };
  }

  const rec = v as Record<string, unknown>;
  const displayName = pickString(rec.displayName, rec.display_name, rec.label);
  const locationType = pickString(rec.locationType, rec.location_type);
  const city = locationType === "country"
    ? null
    : pickString(rec.city);
  const rawCountry = pickString(rec.country, rec.country_name);
  const explicitCountryCode = pickString(rec.country_code, rec.countryCode);
  const displayCountry = displayName && city && displayName.includes(",")
    ? displayName
      .split(",")
      .slice(1)
      .join(",")
      .trim() || null
    : null;
  const inferredCountryCode = rawCountry && /^[A-Za-z]{2,3}$/.test(rawCountry)
    ? rawCountry.toUpperCase()
    : null;
  const countryCode = explicitCountryCode?.toUpperCase() ?? inferredCountryCode;
  const country = rawCountry && !/^[A-Za-z]{2,3}$/.test(rawCountry)
    ? rawCountry
    : locationType === "country" && displayName
    ? displayName
    : displayCountry;
  return { city, country, countryCode };
}

export function buildBeatLocationMatcher(
  location: BeatLocationShape,
): ((text: string) => boolean) | null {
  const cityAliases = location.city ? [location.city] : [];
  const countryAliases = location.countryCode
    ? [...(COUNTRY_ALIAS_MAP[location.countryCode] ?? [])]
    : [];
  if (location.country && !countryAliases.includes(location.country.toLowerCase())) {
    countryAliases.unshift(location.country);
  }

  if (cityAliases.length === 0 && countryAliases.length === 0) {
    return null;
  }

  return (text: string) => {
    const hasCity = cityAliases.some((alias) => containsAlias(text, alias));
    const hasCountry = countryAliases.some((alias) => containsAlias(text, alias));
    if (cityAliases.length > 0) return hasCity || hasCountry;
    return hasCountry;
  };
}

function pickString(...candidates: unknown[]): string | null {
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c.trim();
  }
  return null;
}

function normalizeText(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function containsAlias(text: string, alias: string): boolean {
  const haystack = normalizeText(text);
  const needle = normalizeText(alias);
  if (!needle) return false;
  if (needle.includes(".") || needle.includes("/")) {
    return haystack.includes(needle);
  }
  const pattern = new RegExp(`(^|[^a-z])${escapeRegex(needle)}([^a-z]|$)`);
  return pattern.test(haystack);
}
