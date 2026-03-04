#!/usr/bin/env python3
"""
Log Viewer Utility for Thakii Worker Service
Browse, search, and analyze logs organized by year/month/day
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Generator
import re

# Base logs directory
LOGS_BASE_DIR = os.getenv('LOGS_DIR', 'logs')


class LogViewer:
    """
    Utility class to view and search logs organized by date.
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize log viewer.
        
        Args:
            base_dir: Base directory for logs (defaults to LOGS_BASE_DIR)
        """
        self.base_dir = Path(base_dir or LOGS_BASE_DIR)
    
    def list_available_dates(self) -> List[Dict]:
        """
        List all available log dates.
        
        Returns:
            List of dictionaries with date info and available log files
        """
        dates = []
        
        if not self.base_dir.exists():
            return dates
        
        for year_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if year_dir.is_dir() and year_dir.name.isdigit():
                for month_dir in sorted(year_dir.iterdir(), reverse=True):
                    if month_dir.is_dir() and month_dir.name.isdigit():
                        for day_dir in sorted(month_dir.iterdir(), reverse=True):
                            if day_dir.is_dir() and day_dir.name.isdigit():
                                log_files = list(day_dir.glob('*.log'))
                                if log_files:
                                    total_size = sum(f.stat().st_size for f in log_files)
                                    dates.append({
                                        'date': f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                                        'year': year_dir.name,
                                        'month': month_dir.name,
                                        'day': day_dir.name,
                                        'path': str(day_dir),
                                        'files': [f.name for f in log_files],
                                        'file_count': len(log_files),
                                        'total_size': total_size,
                                        'total_size_readable': self._format_size(total_size)
                                    })
        
        return dates
    
    def get_logs_for_date(self, date: str, log_type: str = None) -> Path:
        """
        Get the log directory/file for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            log_type: Optional log type (api, errors, processing, requests)
        
        Returns:
            Path to log directory or specific log file
        """
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Use YYYY-MM-DD")
        
        log_path = self.base_dir / dt.strftime('%Y') / dt.strftime('%m') / dt.strftime('%d')
        
        if log_type:
            log_path = log_path / f"{log_type}.log"
        
        return log_path
    
    def read_logs(self, date: str, log_type: str = 'api', 
                  limit: int = None, level: str = None) -> Generator[Dict, None, None]:
        """
        Read and parse logs for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            log_type: Log type (api, errors, processing, requests)
            limit: Maximum number of entries to return
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        
        Yields:
            Parsed log entries as dictionaries
        """
        log_path = self.get_logs_for_date(date, log_type)
        
        if not log_path.exists():
            return
        
        count = 0
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if limit and count >= limit:
                    break
                
                try:
                    entry = json.loads(line.strip())
                    
                    # Filter by level if specified
                    if level and entry.get('level') != level.upper():
                        continue
                    
                    yield entry
                    count += 1
                    
                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue
    
    def search_logs(self, query: str, date: str = None, log_type: str = None,
                    days_back: int = 7) -> Generator[Dict, None, None]:
        """
        Search logs for a specific query.
        
        Args:
            query: Search query (regex supported)
            date: Specific date to search (YYYY-MM-DD)
            log_type: Specific log type to search
            days_back: Number of days to search back (if no date specified)
        
        Yields:
            Matching log entries
        """
        pattern = re.compile(query, re.IGNORECASE)
        
        if date:
            dates_to_search = [date]
        else:
            # Get dates for the last N days
            dates_to_search = []
            for i in range(days_back):
                dt = datetime.now() - timedelta(days=i)
                dates_to_search.append(dt.strftime('%Y-%m-%d'))
        
        log_types = [log_type] if log_type else ['api', 'errors', 'processing', 'requests']
        
        for search_date in dates_to_search:
            for lt in log_types:
                try:
                    for entry in self.read_logs(search_date, lt):
                        # Search in the entire entry JSON
                        entry_str = json.dumps(entry)
                        if pattern.search(entry_str):
                            entry['_source_date'] = search_date
                            entry['_source_file'] = lt
                            yield entry
                except Exception:
                    continue
    
    def get_video_logs(self, video_id: str, days_back: int = 30) -> List[Dict]:
        """
        Get all logs for a specific video ID.
        
        Args:
            video_id: Video ID to search for
            days_back: Number of days to search back
        
        Returns:
            List of log entries related to the video
        """
        return list(self.search_logs(video_id, days_back=days_back))
    
    def get_error_summary(self, date: str = None, days_back: int = 7) -> Dict:
        """
        Get a summary of errors.
        
        Args:
            date: Specific date (YYYY-MM-DD)
            days_back: Number of days to analyze
        
        Returns:
            Dictionary with error statistics
        """
        errors_by_type = {}
        errors_by_endpoint = {}
        total_errors = 0
        
        if date:
            dates_to_check = [date]
        else:
            dates_to_check = []
            for i in range(days_back):
                dt = datetime.now() - timedelta(days=i)
                dates_to_check.append(dt.strftime('%Y-%m-%d'))
        
        for check_date in dates_to_check:
            try:
                for entry in self.read_logs(check_date, 'errors'):
                    total_errors += 1
                    
                    error_type = entry.get('error_type', 'Unknown')
                    errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
                    
                    endpoint = entry.get('endpoint', 'Unknown')
                    errors_by_endpoint[endpoint] = errors_by_endpoint.get(endpoint, 0) + 1
            except Exception:
                continue
        
        return {
            'total_errors': total_errors,
            'errors_by_type': dict(sorted(errors_by_type.items(), 
                                          key=lambda x: x[1], reverse=True)),
            'errors_by_endpoint': dict(sorted(errors_by_endpoint.items(), 
                                              key=lambda x: x[1], reverse=True)),
            'period': f"Last {days_back} days" if not date else date
        }
    
    def get_request_stats(self, date: str) -> Dict:
        """
        Get request statistics for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
        
        Returns:
            Dictionary with request statistics
        """
        total_requests = 0
        status_codes = {}
        endpoints = {}
        response_times = []
        
        for entry in self.read_logs(date, 'requests'):
            total_requests += 1
            
            status_code = entry.get('status_code')
            if status_code:
                status_codes[status_code] = status_codes.get(status_code, 0) + 1
            
            endpoint = entry.get('endpoint', 'Unknown')
            endpoints[endpoint] = endpoints.get(endpoint, 0) + 1
            
            response_time = entry.get('response_time')
            if response_time:
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        
        return {
            'date': date,
            'total_requests': total_requests,
            'status_codes': status_codes,
            'endpoints': dict(sorted(endpoints.items(), key=lambda x: x[1], reverse=True)),
            'response_time': {
                'avg_ms': round(avg_response_time, 2),
                'max_ms': round(max_response_time, 2),
                'min_ms': round(min_response_time, 2)
            }
        }
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def print_logs(self, date: str, log_type: str = 'api', 
                   limit: int = 20, level: str = None):
        """Print logs in a readable format."""
        print(f"\n📋 Logs for {date} ({log_type}.log)")
        print("=" * 80)
        
        count = 0
        for entry in self.read_logs(date, log_type, limit, level):
            count += 1
            timestamp = entry.get('local_time', entry.get('timestamp', 'Unknown'))
            level = entry.get('level', 'INFO')
            message = entry.get('message', '')
            
            # Color coding for levels
            level_colors = {
                'DEBUG': '\033[36m',
                'INFO': '\033[32m',
                'WARNING': '\033[33m',
                'ERROR': '\033[31m',
                'CRITICAL': '\033[35m'
            }
            color = level_colors.get(level, '')
            reset = '\033[0m'
            
            print(f"{timestamp} | {color}{level:8}{reset} | {message}")
            
            # Print extra details for errors
            if level in ['ERROR', 'CRITICAL'] and 'exception' in entry:
                print(f"   Exception: {entry['exception'].get('type')}: {entry['exception'].get('message')}")
        
        if count == 0:
            print("No logs found.")
        else:
            print(f"\nTotal: {count} entries")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Thakii Worker Service Log Viewer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available log dates
  python -m core.log_viewer list

  # View today's API logs
  python -m core.log_viewer view --date today --type api

  # View error logs for a specific date
  python -m core.log_viewer view --date 2025-12-22 --type errors

  # Search for a video ID
  python -m core.log_viewer search "direct-abc123"

  # Get error summary for last 7 days
  python -m core.log_viewer summary --days 7

  # Get request statistics for today
  python -m core.log_viewer stats --date today
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available log dates')
    
    # View command
    view_parser = subparsers.add_parser('view', help='View logs for a date')
    view_parser.add_argument('--date', '-d', default='today', 
                            help='Date (YYYY-MM-DD or "today")')
    view_parser.add_argument('--type', '-t', default='api',
                            choices=['api', 'errors', 'processing', 'requests'],
                            help='Log type to view')
    view_parser.add_argument('--limit', '-l', type=int, default=50,
                            help='Maximum entries to show')
    view_parser.add_argument('--level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                            help='Filter by log level')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search logs')
    search_parser.add_argument('query', help='Search query (regex supported)')
    search_parser.add_argument('--date', '-d', help='Specific date to search')
    search_parser.add_argument('--days', type=int, default=7,
                              help='Days to search back')
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Error summary')
    summary_parser.add_argument('--date', '-d', help='Specific date')
    summary_parser.add_argument('--days', type=int, default=7,
                               help='Days to analyze')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Request statistics')
    stats_parser.add_argument('--date', '-d', default='today',
                             help='Date (YYYY-MM-DD or "today")')
    
    args = parser.parse_args()
    viewer = LogViewer()
    
    # Handle 'today' date
    def parse_date(date_str):
        if date_str == 'today':
            return datetime.now().strftime('%Y-%m-%d')
        return date_str
    
    if args.command == 'list':
        dates = viewer.list_available_dates()
        if not dates:
            print("No logs found.")
            return
        
        print("\n📅 Available Log Dates:")
        print("=" * 60)
        for d in dates:
            print(f"  {d['date']} | {d['file_count']} files | {d['total_size_readable']}")
            print(f"     Files: {', '.join(d['files'])}")
        print(f"\nTotal: {len(dates)} dates with logs")
    
    elif args.command == 'view':
        date = parse_date(args.date)
        viewer.print_logs(date, args.type, args.limit, args.level)
    
    elif args.command == 'search':
        date = parse_date(args.date) if args.date else None
        results = list(viewer.search_logs(args.query, date, days_back=args.days))
        
        print(f"\n🔍 Search results for: {args.query}")
        print("=" * 60)
        
        for entry in results[:50]:  # Limit output
            timestamp = entry.get('local_time', entry.get('timestamp', 'Unknown'))
            level = entry.get('level', 'INFO')
            message = entry.get('message', '')
            source = f"{entry.get('_source_date')}/{entry.get('_source_file')}"
            
            print(f"{timestamp} | {level:8} | {message[:60]}...")
            print(f"   Source: {source}")
        
        print(f"\nFound: {len(results)} matching entries")
    
    elif args.command == 'summary':
        date = parse_date(args.date) if args.date else None
        summary = viewer.get_error_summary(date, args.days)
        
        print("\n🚨 Error Summary")
        print("=" * 60)
        print(f"Period: {summary['period']}")
        print(f"Total Errors: {summary['total_errors']}")
        
        print("\nBy Error Type:")
        for error_type, count in list(summary['errors_by_type'].items())[:10]:
            print(f"  {error_type}: {count}")
        
        print("\nBy Endpoint:")
        for endpoint, count in list(summary['errors_by_endpoint'].items())[:10]:
            print(f"  {endpoint}: {count}")
    
    elif args.command == 'stats':
        date = parse_date(args.date)
        stats = viewer.get_request_stats(date)
        
        print(f"\n📊 Request Statistics for {date}")
        print("=" * 60)
        print(f"Total Requests: {stats['total_requests']}")
        
        print("\nStatus Codes:")
        for code, count in sorted(stats['status_codes'].items()):
            print(f"  {code}: {count}")
        
        print("\nResponse Times:")
        print(f"  Average: {stats['response_time']['avg_ms']} ms")
        print(f"  Max: {stats['response_time']['max_ms']} ms")
        print(f"  Min: {stats['response_time']['min_ms']} ms")
        
        print("\nTop Endpoints:")
        for endpoint, count in list(stats['endpoints'].items())[:10]:
            print(f"  {endpoint}: {count}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
