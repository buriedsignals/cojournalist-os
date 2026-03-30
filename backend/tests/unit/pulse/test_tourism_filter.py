"""Tests for is_likely_tourism_content() heuristic filter."""
import pytest
from app.services.news_utils import is_likely_tourism_content


class TestTourismFilter:
    """is_likely_tourism_content() catches travel blogs and tourism guides."""

    def test_travel_domain(self):
        article = {"url": "https://travelsofsarahfay.com/spokane-guide", "title": "Exploring Spokane"}
        assert is_likely_tourism_content(article) is True

    def test_tripadvisor(self):
        article = {"url": "https://www.tripadvisor.com/Attractions-Spokane", "title": "Top Attractions"}
        assert is_likely_tourism_content(article) is True

    def test_lonelyplanet(self):
        article = {"url": "https://www.lonelyplanet.com/usa/spokane", "title": "Spokane Guide"}
        assert is_likely_tourism_content(article) is True

    def test_visit_prefix_domain(self):
        article = {"url": "https://visit-spokane.org/things-to-do", "title": "Plan Your Visit"}
        assert is_likely_tourism_content(article) is True

    def test_tourism_in_domain(self):
        article = {"url": "https://spokane-tourism.com/guide", "title": "Welcome"}
        assert is_likely_tourism_content(article) is True

    def test_things_to_do_title(self):
        article = {"url": "https://genericblog.com/post", "title": "Things to do in Spokane this summer"}
        assert is_likely_tourism_content(article) is True

    def test_travel_guide_title(self):
        article = {"url": "https://anyblog.com/post", "title": "Travel Guide to the Pacific Northwest"}
        assert is_likely_tourism_content(article) is True

    def test_best_places_description(self):
        article = {
            "url": "https://anyblog.com/post",
            "title": "Weekend Ideas",
            "description": "The best places to visit near Spokane for a day trip",
        }
        assert is_likely_tourism_content(article) is True

    def test_local_blog_passes(self):
        article = {"url": "https://localblog.com/post", "title": "Spring Festival This Saturday"}
        assert is_likely_tourism_content(article) is False

    def test_community_event_passes(self):
        article = {"url": "https://spokane-events.org/calendar", "title": "Farmers Market Opens May 1st"}
        assert is_likely_tourism_content(article) is False

    def test_local_news_passes(self):
        article = {"url": "https://spokesman.com/stories/2024/council-vote", "title": "City Council Votes on Budget"}
        assert is_likely_tourism_content(article) is False

    def test_empty_article(self):
        article = {"url": "", "title": ""}
        assert is_likely_tourism_content(article) is False
