#!/usr/bin/env python3
"""
GitHub Repository Health Monitor
A lightweight SRE tool for monitoring GitHub repository metrics and health indicators.

This script demonstrates SRE principles including:
- Resilience: Retry logic, timeout handling, graceful degradation
- Observability: Structured logging, metrics collection, error tracking
- Operational reliability: Configuration management, health checks
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import argparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configuration constants
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.3
DEFAULT_OUTPUT_FILE = "repo_health_report.json"


@dataclass
class RepositoryHealth:
    """Data class for repository health metrics"""
    name: str
    full_name: str
    description: str
    language: str
    stars: int
    forks: int
    open_issues: int
    watchers: int
    size_kb: int
    created_at: str
    updated_at: str
    pushed_at: str
    license: Optional[str]
    health_score: float
    freshness_days: int
    activity_level: str
    timestamp: str


class GitHubAPIClient:
    """Resilient GitHub API client with SRE best practices"""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_RETRIES):
        self.base_url = "https://api.github.com"
        self.timeout = timeout
        self.session = self._create_session(max_retries)
        self.logger = logging.getLogger(__name__)
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set user agent for API best practices
        session.headers.update({
            'User-Agent': 'SRE-Health-Monitor/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        return session
    
    def fetch_repository_data(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Fetch repository data with comprehensive error handling
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Repository data dictionary
            
        Raises:
            requests.RequestException: For API errors
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        
        try:
            self.logger.info(f"Fetching data for {owner}/{repo}")
            start_time = time.time()
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            response_time = time.time() - start_time
            self.logger.info(f"API call completed in {response_time:.2f}s")
            
            # Log rate limit information for operational awareness
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Remaining']
                reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                self.logger.info(f"Rate limit remaining: {remaining}, resets at: {reset_time}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout after {self.timeout}s fetching {owner}/{repo}")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.error(f"Repository {owner}/{repo} not found")
            elif e.response.status_code == 403:
                self.logger.error("API rate limit exceeded or access forbidden")
            else:
                self.logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise


class RepositoryAnalyzer:
    """Analyzes repository data and computes health metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_repository(self, data: Dict[str, Any]) -> RepositoryHealth:
        """
        Analyze repository data and compute health metrics
        
        Args:
            data: Raw repository data from GitHub API
            
        Returns:
            RepositoryHealth object with computed metrics
        """
        try:
            # Extract basic information
            name = data.get('name', 'Unknown')
            full_name = data.get('full_name', 'Unknown')
            description = data.get('description') or 'No description provided'
            language = data.get('language') or 'Not specified'
            
            # Extract metrics
            stars = data.get('stargazers_count', 0)
            forks = data.get('forks_count', 0)
            open_issues = data.get('open_issues_count', 0)
            watchers = data.get('watchers_count', 0)
            size_kb = data.get('size', 0)
            
            # Extract timestamps
            created_at = data.get('created_at', '')
            updated_at = data.get('updated_at', '')
            pushed_at = data.get('pushed_at', '')
            
            # Extract license information
            license_info = data.get('license')
            license_name = license_info.get('name') if license_info else None
            
            # Compute derived metrics
            freshness_days = self._calculate_freshness(pushed_at)
            activity_level = self._assess_activity_level(stars, forks, freshness_days)
            health_score = self._calculate_health_score(stars, forks, open_issues, freshness_days)
            
            return RepositoryHealth(
                name=name,
                full_name=full_name,
                description=description,
                language=language,
                stars=stars,
                forks=forks,
                open_issues=open_issues,
                watchers=watchers,
                size_kb=size_kb,
                created_at=created_at,
                updated_at=updated_at,
                pushed_at=pushed_at,
                license=license_name,
                health_score=health_score,
                freshness_days=freshness_days,
                activity_level=activity_level,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing repository data: {str(e)}")
            raise
    
    def _calculate_freshness(self, pushed_at: str) -> int:
        """Calculate days since last push"""
        if not pushed_at:
            return 9999  # Very stale if no push date
        
        try:
            last_push = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return (now - last_push).days
        except Exception:
            return 9999
    
    def _assess_activity_level(self, stars: int, forks: int, freshness_days: int) -> str:
        """Assess repository activity level"""
        # Weighted score considering popularity and freshness
        popularity_score = min((stars + forks * 2) / 100, 10)  # Cap at 10
        freshness_score = max(10 - freshness_days / 30, 0)  # Decreases with age
        
        combined_score = (popularity_score + freshness_score) / 2
        
        if combined_score >= 7:
            return "High"
        elif combined_score >= 4:
            return "Medium"
        else:
            return "Low"
    
    def _calculate_health_score(self, stars: int, forks: int, open_issues: int, freshness_days: int) -> float:
        """Calculate overall repository health score (0-100)"""
        # Popularity component (0-30 points)
        popularity = min((stars + forks) / 100, 30)
        
        # Freshness component (0-30 points)
        if freshness_days <= 7:
            freshness = 30
        elif freshness_days <= 30:
            freshness = 25
        elif freshness_days <= 90:
            freshness = 15
        elif freshness_days <= 365:
            freshness = 5
        else:
            freshness = 0
        
        # Issue management component (0-20 points)
        if open_issues == 0:
            issue_health = 20
        elif open_issues <= 10:
            issue_health = 15
        elif open_issues <= 50:
            issue_health = 10
        else:
            issue_health = max(20 - open_issues / 10, 0)
        
        # Base health component (20 points for existing repo)
        base_health = 20
        
        return round(popularity + freshness + issue_health + base_health, 1)


class ReportGenerator:
    """Generates human-readable reports"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_console_report(self, health: RepositoryHealth) -> None:
        """Generate a human-readable console report"""
        print("\n" + "="*60)
        print(f"🔍 REPOSITORY HEALTH REPORT")
        print("="*60)
        
        print(f"\n📊 BASIC INFORMATION")
        print(f"Repository: {health.full_name}")
        print(f"Description: {health.description[:80]}{'...' if len(health.description) > 80 else ''}")
        print(f"Primary Language: {health.language}")
        print(f"License: {health.license or 'Not specified'}")
        
        print(f"\n📈 METRICS")
        print(f"⭐ Stars: {health.stars:,}")
        print(f"🔄 Forks: {health.forks:,}")
        print(f"👀 Watchers: {health.watchers:,}")
        print(f"🐛 Open Issues: {health.open_issues:,}")
        print(f"💾 Size: {health.size_kb:,} KB")
        
        print(f"\n🕒 ACTIVITY")
        print(f"Created: {health.created_at[:10]}")
        print(f"Last Updated: {health.updated_at[:10]}")
        print(f"Last Push: {health.pushed_at[:10]} ({health.freshness_days} days ago)")
        
        print(f"\n🎯 HEALTH ASSESSMENT")
        print(f"Overall Health Score: {health.health_score}/100 {self._get_health_emoji(health.health_score)}")
        print(f"Activity Level: {health.activity_level} {self._get_activity_emoji(health.activity_level)}")
        
        # Health recommendations
        print(f"\n💡 RECOMMENDATIONS")
        recommendations = self._generate_recommendations(health)
        for rec in recommendations:
            print(f"• {rec}")
        
        print("\n" + "="*60)
    
    def _get_health_emoji(self, score: float) -> str:
        """Get emoji based on health score"""
        if score >= 80:
            return "🟢"
        elif score >= 60:
            return "🟡"
        else:
            return "🔴"
    
    def _get_activity_emoji(self, level: str) -> str:
        """Get emoji based on activity level"""
        return {"High": "🔥", "Medium": "⚡", "Low": "💤"}.get(level, "❓")
    
    def _generate_recommendations(self, health: RepositoryHealth) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if health.freshness_days > 90:
            recommendations.append("Consider updating the repository - it's been inactive for a while")
        
        if health.open_issues > 20:
            recommendations.append("High number of open issues may indicate maintenance backlog")
        
        if not health.license:
            recommendations.append("Consider adding a license for better legal clarity")
        
        if health.health_score < 50:
            recommendations.append("Repository health is below average - review maintenance practices")
        
        if not recommendations:
            recommendations.append("Repository appears healthy! Keep up the good work.")
        
        return recommendations
    
    def save_to_file(self, health: RepositoryHealth, filename: str) -> None:
        """Save health data to JSON file"""
        try:
            output_path = Path(filename)
            with open(output_path, 'w') as f:
                json.dump(asdict(health), f, indent=2, default=str)
            
            self.logger.info(f"Report saved to {output_path.absolute()}")
            print(f"\n💾 Report saved to: {output_path.absolute()}")
            
        except Exception as e:
            self.logger.error(f"Failed to save report: {str(e)}")
            print(f"⚠️  Failed to save report: {str(e)}")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with appropriate level"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='GitHub Repository Health Monitor - An SRE tool for repository analysis'
    )
    
    parser.add_argument(
        'repository',
        help='Repository in format owner/repo (e.g., nodejs/node)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default=DEFAULT_OUTPUT_FILE,
        help=f'Output file for JSON report (default: {DEFAULT_OUTPUT_FILE})'
    )
    
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f'Request timeout in seconds (default: {DEFAULT_TIMEOUT})'
    )
    
    parser.add_argument(
        '--retries', '-r',
        type=int,
        default=DEFAULT_RETRIES,
        help=f'Number of retries for failed requests (default: {DEFAULT_RETRIES})'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--no-file',
        action='store_true',
        help='Skip saving to file, console output only'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main function with comprehensive error handling"""
    args = parse_arguments()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Parse repository argument
        if '/' not in args.repository:
            print("❌ Error: Repository must be in format 'owner/repo'")
            return 1
        
        owner, repo = args.repository.split('/', 1)
        
        # Initialize components
        client = GitHubAPIClient(timeout=args.timeout, max_retries=args.retries)
        analyzer = RepositoryAnalyzer()
        reporter = ReportGenerator()
        
        print(f"🚀 Analyzing repository: {owner}/{repo}")
        
        # Fetch and analyze data
        repo_data = client.fetch_repository_data(owner, repo)
        health = analyzer.analyze_repository(repo_data)
        
        # Generate reports
        reporter.generate_console_report(health)
        
        if not args.no_file:
            reporter.save_to_file(health, args.output)
        
        logger.info("Repository analysis completed successfully")
        return 0
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {str(e)}")
        logger.error(f"API error: {str(e)}")
        return 1
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
