"""
Email notifications via Resend API.

PURPOSE: Send localized scout notification emails with markdown-to-HTML
conversion. Supports both Page Scout (criteria match) and Smart Scout
(new facts digest) notification formats.

DEPENDS ON: config (Resend API key, from email), http_client (connection pooling),
    email_translations (localized strings, title translation)
USED BY: routers/pulse.py, services/scout_service.py
"""
from __future__ import annotations

import asyncio
import html
import logging
import re

from app.config import settings
from app.services.http_client import get_http_client
from app.services.email_translations import get_string, translate_titles_batch

logger = logging.getLogger(__name__)


def group_facts_by_source(facts: list, source_limit: int = 5) -> list:
    """
    Group facts by source_url for cleaner email display.
    Each unique source appears once with all its facts combined.
    """
    grouped = {}
    order = []

    for idx, fact in enumerate(facts):
        # Use source_url as key, fallback to unique key for URL-less facts
        url = fact.get("source_url") or f"__no_url_{idx}__"
        if url not in grouped:
            grouped[url] = {
                "title": fact.get("source_title", "Untitled"),
                "url": fact.get("source_url", ""),  # Keep empty for URL-less
                "source": fact.get("source_domain", ""),
                "statements": []
            }
            order.append(url)
        grouped[url]["statements"].append(fact.get("statement", ""))

    # Build articles with combined summaries
    result = []
    for url in order[:source_limit]:
        source = grouped[url]
        statements = source["statements"]

        # Single fact: no bullets. Multiple: bullet list
        if len(statements) == 1:
            summary = statements[0]
        else:
            summary = "\n".join(f"• {s}" for s in statements)

        result.append({
            "title": source["title"],
            "summary": summary,
            "url": source["url"],
            "source": source["source"]
        })

    return result


def markdown_to_html(text: str, accent_color: str = "#7c6fc7") -> str:
    """
    Convert markdown to email-safe HTML.

    Supports:
    - Headers: ## and ###
    - Bold: **text**
    - Lists: - item, * item, • item
    - Links: [text](url)
    - Paragraph breaks
    """
    if not text:
        return ""

    # Escape HTML entities first (but preserve our own HTML we'll add)
    lines = text.split('\n')
    result_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Handle headers
        if stripped.startswith('### '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(f'<h3 style="margin: 16px 0 8px 0; font-size: 16px; color: #333;">{html.escape(stripped[4:])}</h3>')
            continue
        elif stripped.startswith('## '):
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(f'<h2 style="margin: 20px 0 12px 0; font-size: 18px; color: #333;">{html.escape(stripped[3:])}</h2>')
            continue

        # Handle list items
        list_match = re.match(r'^[-*•]\s+(.+)$', stripped)
        if list_match:
            if not in_list:
                result_lines.append('<ul style="margin: 8px 0; padding-left: 20px;">')
                in_list = True
            item_content = list_match.group(1)
            # Process inline formatting for list items
            item_content = _process_inline_markdown(item_content, accent_color)
            result_lines.append(f'<li style="margin: 4px 0; color: #333;">{item_content}</li>')
            continue

        # Close list if we're no longer in a list item
        if in_list and stripped:
            result_lines.append('</ul>')
            in_list = False

        # Handle empty lines (paragraph breaks)
        if not stripped:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append('<br>')
            continue

        # Regular paragraph - process inline formatting
        processed = _process_inline_markdown(stripped, accent_color)
        result_lines.append(f'<p style="margin: 8px 0; color: #333; line-height: 1.6;">{processed}</p>')

    # Close any unclosed list
    if in_list:
        result_lines.append('</ul>')

    return '\n'.join(result_lines)


def _process_inline_markdown(text: str, accent_color: str) -> str:
    """Process inline markdown: bold and links.

    Security: HTML-escapes all text first, then applies markdown formatting.
    This prevents HTML injection via AI-generated summaries or user input.
    """
    # Step 1: Extract markdown constructs before escaping
    # We'll replace them with placeholders, escape, then restore as HTML

    # Extract bold markers and link constructs
    bold_parts = []
    link_parts = []

    def _save_bold(m):
        idx = len(bold_parts)
        bold_parts.append(m.group(1))
        return f"\x00BOLD{idx}\x00"

    def _save_link(m):
        idx = len(link_parts)
        link_parts.append((m.group(1), m.group(2)))
        return f"\x00LINK{idx}\x00"

    # Extract markdown constructs (order matters: links first since they may contain bold)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _save_link, text)
    text = re.sub(r'\*\*([^*]+)\*\*', _save_bold, text)

    # Step 2: Escape all remaining HTML
    text = html.escape(text)

    # Step 3: Restore markdown constructs as safe HTML
    for idx, content in enumerate(bold_parts):
        text = text.replace(f"\x00BOLD{idx}\x00", f"<strong>{html.escape(content)}</strong>")

    for idx, (link_text, link_url) in enumerate(link_parts):
        safe_text = html.escape(link_text)
        safe_url = html.escape(link_url)
        text = text.replace(
            f"\x00LINK{idx}\x00",
            f'<a href="{safe_url}" style="color: {accent_color}; text-decoration: none;">{safe_text}</a>'
        )

    return text


def _render_article_cards(articles: list[dict], accent_color: str, limit: int = 5) -> str:
    """Render a list of article dicts as styled HTML cards."""
    cards_html = ""
    for article in articles[:limit]:
        url = html.escape(article.get('url', '#'))
        title = html.escape(article.get('title', 'Untitled'))
        article_summary = article.get('summary', article.get('description', ''))
        if article_summary:
            article_summary = html.escape(article_summary)
            if '\n' in article_summary:
                lines = article_summary.split('\n')
                article_summary = '<br>'.join(lines[:5])
                if len(lines) > 5:
                    article_summary += '<br>...'
            elif len(article_summary) > 150:
                article_summary = article_summary[:150] + "..."
        source = html.escape(article.get('source', ''))
        source_html = f'<span style="font-size: 12px; color: #999;">{source}</span>' if source else ''

        cards_html += f"""
            <div style="margin-bottom: 12px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
                <a href="{url}" style="color: {accent_color}; text-decoration: none; font-weight: 600;">
                    {title}
                </a>
                <p style="margin: 8px 0 0 0; color: #666; font-size: 14px;">
                    {article_summary}
                </p>
                {source_html}
            </div>
            """
    return cards_html


class NotificationService:
    """Send email notifications via Resend."""

    RESEND_URL = "https://api.resend.com/emails"

    def _build_email_html(
        self,
        header_title: str,
        header_subtitle: str,
        header_gradient: tuple[str, str] | str,
        accent_color: str,
        context_label: str,
        summary: str,
        articles: list[dict],
        articles_section_title: str,
        extra_content: str = "",
        cta_text: str = "",
        post_content: str = "",
    ) -> str:
        """
        Build unified email HTML template.

        Args:
            header_title: Main title in header (e.g., "Alert Match!", "Local Pulse Update")
            header_subtitle: Subtitle in header (scout name)
            header_gradient: Tuple of (start_color, end_color) or single color string
            accent_color: Color for borders, links, labels
            context_label: Context text below header (e.g., "TROMSØ, NORWAY")
            summary: Main markdown content
            articles: List of article dicts with title, summary, url, source (optional)
            articles_section_title: Section title (e.g., "Top Stories", "Matching Results")
            extra_content: Additional HTML content (e.g., criteria box)
            cta_text: Call-to-action button text (default: "View in coJournalist")
            post_content: Additional HTML inserted after articles section (e.g., government section)
        """
        # Build gradient or solid background
        if isinstance(header_gradient, tuple):
            bg_style = f"linear-gradient(135deg, {header_gradient[0]}, {header_gradient[1]})"
        else:
            bg_style = header_gradient

        articles_html = _render_article_cards(articles, accent_color)

        # Build articles section (only if articles exist)
        articles_section = ""
        if articles:
            articles_section = f"""
            <h3 style="margin: 0 0 16px 0; color: #333;">{articles_section_title}</h3>
            {articles_html}
            """

        # Convert markdown summary to HTML
        summary_html = markdown_to_html(summary, accent_color)

        # Build CTA section only when cta_text is provided
        cta_section = ""
        if cta_text:
            cta_section = f"""
            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center;">
                <a href="https://cojournalist.ai" style="color: {accent_color}; text-decoration: none; font-size: 14px;">
                    {cta_text}
                </a>
            </div>"""

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto;">
        <div style="background: {bg_style}; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">{header_title}</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">{header_subtitle}</p>
        </div>
        <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <div style="margin-bottom: 16px;">
                <span style="font-size: 12px; text-transform: uppercase; color: {accent_color}; font-weight: 600;">
                    {context_label}
                </span>
            </div>

            {extra_content}

            <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 24px; border-left: 4px solid {accent_color};">
                {summary_html}
            </div>

            {articles_section}

            {post_content}

            {cta_section}
        </div>
    </div>
</body>
</html>
"""

    async def send_scout_alert(
        self,
        to_email: str,
        scout_name: str,
        url: str,
        criteria: str,
        summary: str,
        language: str = "en",
        matched_url: str = "",
        matched_title: str = "",
    ) -> bool:
        """Send email alert when web scout criteria is met."""
        # Get localized strings
        monitoring_url_label = get_string("monitoring_url", language)
        criteria_label = get_string("criteria", language)
        header_title = get_string("scout_alert", language)
        context_label = get_string("page_scout", language)

        # Remove the "View in coJournalist" CTA for all Page Scout emails
        cta_text = ""

        # Escape user-controlled values for HTML injection prevention
        url_escaped = html.escape(url)
        scout_name_escaped = html.escape(scout_name)
        criteria_escaped = html.escape(criteria) if criteria else ""

        # Build criteria info as extra content
        criteria_section = ""
        if criteria:
            criteria_section = f"""
            <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
                <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">{criteria_label}</p>
                <p style="margin: 0; color: #333;">{criteria_escaped}</p>
            </div>
            """

        # Build article card for matched content
        articles = []
        articles_section_title = ""
        if matched_url and matched_title:
            articles_section_title = get_string("see_what_matched", language)
            articles = [{
                "title": matched_title,
                "url": matched_url,
                "summary": "",
                "source": "",
            }]

        extra_content = f"""
            <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
                <p style="margin: 0 0 4px 0; font-size: 12px; color: #666; text-transform: uppercase;">{monitoring_url_label}</p>
                <a href="{url_escaped}" style="color: #2563eb; text-decoration: none; word-break: break-all;">{url_escaped}</a>
            </div>
            {criteria_section}
        """

        html_content = self._build_email_html(
            header_title=header_title,
            header_subtitle=scout_name_escaped,
            header_gradient="#1a1a2e",
            accent_color="#2563eb",
            context_label=context_label,
            summary=summary,
            articles=articles,
            articles_section_title=articles_section_title,
            extra_content=extra_content,
            cta_text=cta_text,
        )

        return await self._send_email_with_retry(
            to_email=to_email,
            subject=f"[coJournalist] {header_title} {scout_name}",
            html_content=html_content
        )

    async def _send_email_with_retry(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        max_retries: int = 3
    ) -> bool:
        """Send email with retry logic for reliability."""
        last_error = None
        client = await get_http_client()

        for attempt in range(max_retries):
            try:
                response = await client.post(
                    self.RESEND_URL,
                    headers={
                        "Authorization": f"Bearer {settings.resend_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": "coJournalist <info@cojournalist.ai>",
                        "to": [to_email],
                        "subject": subject,
                        "html": html_content,
                        "reply_to": "info@cojournalist.ai"
                    }
                )

                if response.status_code == 200:
                    logger.info(f"Email sent successfully for user (subject: {subject})")
                    return True

                # Client error (4xx) - don't retry
                if response.status_code < 500:
                    logger.error(f"Email failed with client error: {response.text}")
                    return False

                # Server error (5xx) - retry with backoff
                last_error = f"HTTP {response.status_code}: {response.text}"

            except Exception as e:
                last_error = str(e)

            # Exponential backoff
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                logger.warning(f"Email attempt {attempt + 1} failed, retrying in {delay}s: {last_error}")
                await asyncio.sleep(delay)

        logger.error(f"Email failed after {max_retries} attempts: {last_error}")
        return False

    async def _translate_article_titles(
        self,
        articles: list[dict],
        language: str,
    ) -> list[dict]:
        """
        Translate article titles to target language.

        Creates a shallow copy of the articles list to avoid mutating the input.
        Returns the translated copy (or original if no translation needed).

        Args:
            articles: List of article dicts with 'title' key
            language: Target language code (e.g., "en", "no", "de")

        Returns:
            New list with translated titles (original list unchanged)
        """
        if not articles or language == "en":
            return articles or []

        # Create shallow copy to avoid mutating input
        translated_articles = [dict(article) for article in articles]

        titles = [a.get("title", "") for a in translated_articles]
        translated_titles = await translate_titles_batch(titles, language)

        for i, article in enumerate(translated_articles):
            if i < len(translated_titles):
                article["title"] = translated_titles[i]

        return translated_articles

    async def send_pulse_alert(
        self,
        to_email: str,
        scout_name: str,
        location: str = None,
        summary: str = "",
        articles: list = None,
        topic: str = None,
        language: str = "en",
        gov_articles: list = None,
        gov_summary: str = "",
    ) -> bool:
        """
        Send Pulse alert email.

        Always sends notification regardless of content (pulse mode always notifies).
        Optionally includes a Government & Municipal section when gov_articles are provided.
        """
        # Get localized strings
        header_title = get_string("smart_scout", language)
        section_title = get_string("top_stories", language)
        cta_text = ""

        # Escape user-controlled values for HTML injection prevention
        scout_name_escaped = html.escape(scout_name)

        # Translate article titles (creates copy, doesn't mutate input)
        translated_articles = await self._translate_article_titles(articles or [], language)

        # Build conditional subject and context (topic takes precedence)
        if topic:
            subject = f"{header_title}: {topic} - {scout_name}"
            context_label = html.escape(topic.upper())
        else:
            subject = f"{header_title}: {location} - {scout_name}"
            context_label = html.escape((location or "").upper())

        # Build government section HTML if gov articles exist
        post_content = ""
        if gov_articles:
            translated_gov = await self._translate_article_titles(gov_articles, language)
            gov_section_title = get_string("government_municipal", language)
            accent = "#7c3aed"

            # Build gov summary box
            gov_summary_html = ""
            if gov_summary:
                gov_summary_converted = markdown_to_html(gov_summary, accent)
                gov_summary_html = f"""
                <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 16px; border-left: 4px solid {accent};">
                    {gov_summary_converted}
                </div>
                """

            gov_cards_html = _render_article_cards(translated_gov, accent)

            post_content = f"""
            <div style="margin-top: 24px; padding-top: 20px; border-top: 2px solid #e5e7eb;">
                <h3 style="margin: 0 0 16px 0; color: #333;">{gov_section_title}</h3>
                {gov_summary_html}
                {gov_cards_html}
            </div>
            """

        html_content = self._build_email_html(
            header_title=header_title,
            header_subtitle=scout_name_escaped,
            header_gradient=("#7c3aed", "#6d28d9"),
            accent_color="#7c3aed",
            context_label=context_label,
            summary=summary,
            articles=translated_articles,
            articles_section_title=section_title,
            cta_text=cta_text,
            post_content=post_content,
        )

        return await self._send_email_with_retry(
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )

    async def send_civic_alert(
        self,
        to_email: str,
        scout_name: str,
        summary: str = "",
        language: str = "en",
    ) -> bool:
        """Send Civic Scout notification email.

        Used for both execution alerts (new promises found) and promise-checker
        digests (upcoming deadlines). Uses an amber gradient to distinguish
        Civic Scout emails from Pulse (purple) and Page Scout (dark-blue) ones.
        """
        header_title = get_string("civic_scout", language)
        scout_name_escaped = html.escape(scout_name)

        html_content = self._build_email_html(
            header_title=header_title,
            header_subtitle=scout_name_escaped,
            header_gradient=("#d97706", "#b45309"),  # amber gradient
            accent_color="#d97706",
            context_label=get_string("civic_scout", language),
            summary=summary,
            articles=[],
            articles_section_title="",
        )

        return await self._send_email_with_retry(
            to_email=to_email,
            subject=f"[coJournalist] {header_title}: {scout_name}",
            html_content=html_content,
        )
