#!/usr/bin/env python3
"""
Unit tests for GitHub Repository Health Monitor

This test suite covers:
- API client functionality with mocked responses
- Repository analysis logic
- Error handling scenarios
- Edge cases and boundary conditions
"""

import json
import pytest
import responses
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, mock_open

from github_monitor import (
    GitHubAPIClient,
    RepositoryAnalyzer,
    ReportGenerator,
    RepositoryHealth
)


class TestGitHubAPIClient:
    """Test cases for GitHubAPIClient"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.client = GitHubAPIClient(timeout=5, max_retries=2)
    
    @responses.activate
    def test_fetch_repository_data_success(self):
        """Test successful API call"""
        # Mock response data
        mock_data = {
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "description": "A test repository",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 5,
            "watchers_count": 15,
            "size": 1024,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-12-01T00:00:00Z",
            "pushed_at": "2023-12-01T00:00:00Z",
            "license": {"name": "MIT License"}
        }
        
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/test-repo",
            json=mock_data,
            status=200,
            headers={"X-RateLimit-Remaining": "4999"}
        )
        
        result = self.client.fetch_repository_data("owner", "test-repo")
        
        assert result == mock_data
        assert len(responses.calls) == 1
    
    @responses.activate
    def test_fetch_repository_data_not_found(self):
        """Test 404 error handling"""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/nonexistent",
            status=404
        )
        
        with pytest.raises(Exception):
            self.client.fetch_repository_data("owner", "nonexistent")
    
    @responses.activate
    def test_fetch_repository_data_rate_limit(self):
        """Test rate limit error handling"""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/test-repo",
            status=403,
            json={"message": "API rate limit exceeded"}
        )
        
        with pytest.raises(Exception):
            self.client.fetch_repository_data("owner", "test-repo")
    
    @responses.activate
    def test_fetch_repository_data_with_retries(self):
        """Test retry mechanism"""
        mock_data = {"name": "test-repo"}
        
        # First call fails, second succeeds
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/test-repo",
            status=500
        )
        responses.add(
            responses.GET,
            "https://api.github.com/repos/owner/test-repo",
            json=mock_data,
            status=200
        )
        
        result = self.client.fetch_repository_data("owner", "test-repo")
        assert result == mock_data
        assert len(responses.calls) == 2


class TestRepositoryAnalyzer:
    """Test cases for RepositoryAnalyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = RepositoryAnalyzer()
        
        # Sample repository data
        self.sample_data = {
            "name": "awesome-project",
            "full_name": "owner/awesome-project",
            "description": "An awesome test project",
            "language": "Python",
            "stargazers_count": 1500,
            "forks_count": 300,
            "open_issues_count": 10,
            "watchers_count": 1200,
            "size": 2048,
            "created_at": "2022-01-01T00:00:00Z",
            "updated_at": "2023-12-01T00:00:00Z",
            "pushed_at": "2023-12-01T00:00:00Z",
            "license": {"name": "Apache License 2.0"}
        }
    
    def test_analyze_repository_success(self):
        """Test successful repository analysis"""
        result = self.analyzer.analyze_repository(self.sample_data)
        
        assert isinstance(result, RepositoryHealth)
        assert result.name == "awesome-project"
        assert result.full_name == "owner/awesome-project"
        assert result.description == "An awesome test project"
        assert result.language == "Python"
        assert result.stars == 1500
        assert result.forks == 300
        assert result.open_issues == 10
        assert result.license == "Apache License 2.0"
        assert result.health_score > 0
        assert result.activity_level in ["High", "Medium", "Low"]
    
    def test_analyze_repository_missing_fields(self):
        """Test analysis with missing optional fields"""
        minimal_data = {
            "name": "minimal-repo",
            "full_name": "owner/minimal-repo"
        }
        
        result = self.analyzer.analyze_repository(minimal_data)
        
        assert result.name == "minimal-repo"
        assert result.description == "No description provided"
        assert result.language == "Not specified"
        assert result.stars == 0
        assert result.license is None
    
    def test_calculate_freshness_recent(self):
        """Test freshness calculation for recent push"""
        recent_push = datetime.now(timezone.utc).isoformat()
        freshness = self.analyzer._calculate_freshness(recent_push)
        assert freshness == 0
    
    def test_calculate_freshness_old(self):
        """Test freshness calculation for old push"""
        old_push = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        freshness = self.analyzer._calculate_freshness(old_push)
        assert freshness == 30
    
    def test_calculate_freshness_invalid_date(self):
        """Test freshness calculation with invalid date"""
        freshness = self.analyzer._calculate_freshness("invalid-date")
        assert freshness == 9999
    
    def test_assess_activity_level_high(self):
        """Test high activity level assessment"""
        activity = self.analyzer._assess_activity_level(1000, 200, 1)
        assert activity == "High"
    
    def test_assess_activity_level_low(self):
        """Test low activity level assessment"""
        activity = self.analyzer._assess_activity_level(5, 1, 365)
        assert activity == "Low"
    
    def test_calculate_health_score_healthy(self):
        """Test health score calculation for healthy repo"""
        score = self.analyzer._calculate_health_score(1000, 200, 5, 7)
        assert score >= 80
    
    def test_calculate_health_score_unhealthy(self):
        """Test health score calculation for unhealthy repo"""
        score = self.analyzer._calculate_health_score(0, 0, 100, 1000)
        assert score < 50


class TestReportGenerator:
    """Test cases for ReportGenerator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.reporter = ReportGenerator()
        self.sample_health = RepositoryHealth(
            name="test-repo",
            full_name="owner/test-repo",
            description="A test repository for unit testing",
            language="Python",
            stars=500,
            forks=100,
            open_issues=5,
            watchers=400,
            size_kb=1024,
            created_at="2022-01-01T00:00:00Z",
            updated_at="2023-12-01T00:00:00Z",
            pushed_at="2023-12-01T00:00:00Z",
            license="MIT License",
            health_score=85.5,
            freshness_days=7,
            activity_level="High",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def test_generate_console_report(self, capsys):
        """Test console report generation"""
        self.reporter.generate_console_report(self.sample_health)
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "REPOSITORY HEALTH REPORT" in output
        assert "owner/test-repo" in output
        assert "Stars: 500" in output
        assert "Health Score: 85.5/100" in output
        assert "Activity Level: High" in output
    
    def test_get_health_emoji(self):
        """Test health emoji selection"""
        assert self.reporter._get_health_emoji(90) == "🟢"
        assert self.reporter._get_health_emoji(70) == "🟡"
        assert self.reporter._get_health_emoji(40) == "🔴"
    
    def test_get_activity_emoji(self):
        """Test activity emoji selection"""
        assert self.reporter._get_activity_emoji("High") == "🔥"
        assert self.reporter._get_activity_emoji("Medium") == "⚡"
        assert self.reporter._get_activity_emoji("Low") == "💤"
    
    def test_generate_recommendations_healthy(self):
        """Test recommendations for healthy repository"""
        recommendations = self.reporter._generate_recommendations(self.sample_health)
        assert "Repository appears healthy!" in recommendations[0]
    
    def test_generate_recommendations_stale(self):
        """Test recommendations for stale repository"""
        stale_health = self.sample_health
        stale_health.freshness_days = 120
        
        recommendations = self.reporter._generate_recommendations(stale_health)
        assert any("inactive" in rec for rec in recommendations)
    
    def test_generate_recommendations_many_issues(self):
        """Test recommendations for repository with many issues"""
        issue_health = self.sample_health
        issue_health.open_issues = 50
        
        recommendations = self.reporter._generate_recommendations(issue_health)
        assert any("issues" in rec for rec in recommendations)
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.absolute")
    def test_save_to_file_success(self, mock_absolute, mock_file):
        """Test successful file saving"""
        mock_absolute.return_value = "/tmp/test_report.json"
        
        self.reporter.save_to_file(self.sample_health, "test_report.json")
        
        mock_file.assert_called_once()
        written_data = mock_file().write.call_args_list
        
        # Verify JSON was written
        json_content = "".join(call[0][0] for call in written_data)
        parsed_data = json.loads(json_content)
        
        assert parsed_data["name"] == "test-repo"
        assert parsed_data["health_score"] == 85.5


class TestIntegration:
    """Integration tests"""
    
    def setup_method(self):
        """Set up integration test fixtures"""
        self.client = GitHubAPIClient()
        self.analyzer = RepositoryAnalyzer()
        self.reporter = ReportGenerator()
    
    @responses.activate
    def test_full_pipeline(self):
        """Test the complete analysis pipeline"""
        # Mock API response
        mock_data = {
            "name": "integration-test",
            "full_name": "test/integration-test",
            "description": "Integration test repository",
            "language": "TypeScript",
            "stargazers_count": 42,
            "forks_count": 7,
            "open_issues_count": 2,
            "watchers_count": 35,
            "size": 512,
            "created_at": "2023-06-01T00:00:00Z",
            "updated_at": "2023-12-15T00:00:00Z",
            "pushed_at": "2023-12-15T00:00:00Z",
            "license": {"name": "BSD 3-Clause License"}
        }
        
        responses.add(
            responses.GET,
            "https://api.github.com/repos/test/integration-test",
            json=mock_data,
            status=200
        )
        
        # Execute full pipeline
        repo_data = self.client.fetch_repository_data("test", "integration-test")
        health = self.analyzer.analyze_repository(repo_data)
        
        # Verify results
        assert health.name == "integration-test"
        assert health.language == "TypeScript"
        assert health.stars == 42
        assert health.license == "BSD 3-Clause License"
        assert health.health_score > 0
        assert health.activity_level in ["High", "Medium", "Low"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=github_monitor", "--cov-report=term-missing"])
            