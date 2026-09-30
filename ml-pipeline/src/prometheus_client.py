"""
Prometheus API Client for fetching metrics
"""

import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime

logger = logging.getLogger(__name__)

class PrometheusClient:
    """Simple Prometheus client for fetching metrics data"""
    _connection_cache: Dict[str, tuple[bool, float]] = {}

    def __init__(self, url: str = "http://localhost:9090", timeout: int = 5):
        """
        Initialize Prometheus client
        
        Args:
            url: Prometheus server URL
            timeout: Request timeout in seconds
        """
        self.url = url
        self.timeout = timeout
        self.client = PrometheusConnect(
            url=url,
            headers=None,
            disable_ssl=False,
            timeout=timeout
        )
        self.is_connected = self._check_connection()
    
    def _check_connection(self) -> bool:
        """Check if Prometheus is reachable with cached result to avoid latency"""
        now = time.time() if "time" in globals() else datetime.now().timestamp()
        if self.url in self._connection_cache:
            status, last_checked = self._connection_cache[self.url]
            if now - last_checked < 10.0:
                return status

        try:
            # Fast ping with 0.5s timeout
            resp = requests.get(f"{self.url.rstrip('/')}/-/healthy", timeout=0.5)
            connected = resp.status_code == 200
        except Exception:
            connected = False

        self._connection_cache[self.url] = (connected, now)
        if connected:
            logger.info(f"✅ Connected to Prometheus at {self.url}")
        else:
            logger.warning(f"⚠️ Prometheus not reachable at {self.url}")
        return connected
    
    def query_instant(self, query: str, time: Optional[str] = None) -> pd.DataFrame:
        """
        Execute instant query (single point in time)
        
        Args:
            query: PromQL query string
            time: Timestamp (optional, defaults to now)
        
        Returns:
            DataFrame with metric values
        """
        try:
            result = self.client.custom_query(query=query, time=time)
            return self._parse_query_result(result)
        except Exception as e:
            logger.error(f"❌ Instant query failed: {query} - {e}")
            return pd.DataFrame()
    
    def query_range(
        self, 
        query: str, 
        start_time: str, 
        end_time: str = "now", 
        step: str = "15s"
    ) -> pd.DataFrame:
        """
        Execute range query (time series)
        
        Args:
            query: PromQL query string
            start_time: Start timestamp (e.g., "-1h", "-30m", or ISO format)
            end_time: End timestamp (default: "now")
            step: Resolution step (e.g., "15s", "1m")
        
        Returns:
            DataFrame with time series data
        """
        try:
            result = self.client.custom_query_range(
                query=query,
                start_time=parse_datetime(start_time),
                end_time=parse_datetime(end_time),
                step=step
            )
            return self._parse_range_result(result)
        except Exception as e:
            logger.error(f"❌ Range query failed: {query} - {e}")
            return pd.DataFrame()
    
    def _parse_query_result(self, result: List[Dict]) -> pd.DataFrame:
        """Parse instant query result into DataFrame"""
        if not result:
            return pd.DataFrame()
        
        data = []
        for item in result:
            metric = item.get('metric', {})
            value = item.get('value', [None, None])
            
            row = {
                'timestamp': datetime.fromtimestamp(value[0]) if value[0] else None,
                'value': float(value[1]) if value[1] else None,
                **{f'metric_{k}': v for k, v in metric.items()}
            }
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _parse_range_result(self, result: List[Dict]) -> pd.DataFrame:
        """Parse range query result into DataFrame"""
        if not result:
            return pd.DataFrame()
        
        data = []
        for item in result:
            metric = item.get('metric', {})
            values = item.get('values', [])
            
            for timestamp, value in values:
                row = {
                    'timestamp': datetime.fromtimestamp(timestamp),
                    'value': float(value) if value else None,
                    **{f'metric_{k}': v for k, v in metric.items()}
                }
                data.append(row)
        
        return pd.DataFrame(data)
    
    def get_metrics_list(self) -> List[str]:
        """Get list of all available metric names"""
        try:
            metrics = self.client.all_metrics()
            return metrics
        except Exception as e:
            logger.error(f"❌ Failed to get metrics: {e}")
            return []
    
    def get_targets(self) -> List[Dict]:
        """Get list of all targets being scraped"""
        try:
            targets = self.client.get_targets()
            return targets
        except Exception as e:
            logger.error(f"❌ Failed to get targets: {e}")
            return []