/**
 * CSV Parser -- parse and preview CSV data from extraction results.
 *
 * USED BY: utils/scraper/index.ts (re-exported), DataExtract.svelte
 * DEPENDS ON: (none)
 *
 * Handles quoted fields with commas, escaped quotes, newlines inside
 * quoted fields, and optional row limits for preview rendering.
 */

export interface ParsedCSVData {
	headers: string[];
	rows: string[][];
	totalRows: number;
}

/**
 * Parse CSV text into structured data.
 * Handles RFC 4180 quoting: newlines and commas inside quoted fields.
 *
 * @param csvText - Raw CSV content as string
 * @param maxRows - Maximum number of rows to parse (default: all rows)
 * @returns Parsed CSV data with headers and rows
 */
export function parseCSV(csvText: string, maxRows?: number): ParsedCSVData {
	const trimmed = csvText.trim();
	if (trimmed.length === 0) {
		return { headers: [], rows: [], totalRows: 0 };
	}

	const records = parseCSVRecords(trimmed);

	if (records.length === 0) {
		return { headers: [], rows: [], totalRows: 0 };
	}

	const headers = records[0];
	const allRows = records.slice(1).filter((r) => r.length > 0 && r.some((f) => f !== ''));

	const rows = maxRows ? allRows.slice(0, maxRows) : allRows;

	return {
		headers,
		rows,
		totalRows: allRows.length
	};
}

/**
 * Parse CSV text into an array of records (each record is an array of fields).
 * Correctly handles newlines inside quoted fields per RFC 4180.
 */
function parseCSVRecords(text: string): string[][] {
	const records: string[][] = [];
	let fields: string[] = [];
	let currentField = '';
	let inQuotes = false;

	for (let i = 0; i < text.length; i++) {
		const char = text[i];
		const nextChar = text[i + 1];

		if (char === '"') {
			if (!inQuotes) {
				inQuotes = true;
			} else if (nextChar === '"') {
				// Escaped quote
				currentField += '"';
				i++;
			} else {
				// End of quoted field
				inQuotes = false;
			}
		} else if (char === ',' && !inQuotes) {
			fields.push(currentField);
			currentField = '';
		} else if (char === '\n' && !inQuotes) {
			fields.push(currentField);
			currentField = '';
			records.push(fields);
			fields = [];
		} else if (char === '\r' && !inQuotes) {
			// Handle \r\n line endings — skip \r, let \n handle the record break
			if (nextChar !== '\n') {
				fields.push(currentField);
				currentField = '';
				records.push(fields);
				fields = [];
			}
		} else {
			currentField += char;
		}
	}

	// Final field/record
	fields.push(currentField);
	if (fields.some((f) => f !== '')) {
		records.push(fields);
	}

	return records;
}

/**
 * Read a Blob as text.
 *
 * @param blob - Blob to read
 * @returns Promise resolving to text content
 */
export async function readBlobAsText(blob: Blob): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result as string);
		reader.onerror = () => reject(new Error('Failed to read blob'));
		reader.readAsText(blob);
	});
}

/**
 * Parse CSV blob and extract preview data.
 *
 * @param csvBlob - CSV file as Blob
 * @param maxRows - Maximum number of rows to include in preview (default: 10)
 * @returns Parsed CSV preview data
 */
export async function parseCSVBlob(csvBlob: Blob, maxRows: number = 10): Promise<ParsedCSVData> {
	const csvText = await readBlobAsText(csvBlob);
	return parseCSV(csvText, maxRows);
}
