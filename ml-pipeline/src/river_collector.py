"""
River-based data collector for streaming metrics from Prometheus
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from river import stream
from river import metrics as river_metrics

from .prometheus_client import PrometheusClient

logger = logging.getLogger(__name__)


class RiverCollector:
    """
    Simple River-based collector that streams data from Prometheus
    
    This is just for DATA COLLECTION - no model training or updates
    """
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        service_name: str = "default",
        batch_size: int = 100,
        poll_interval: int = 60,  # seconds
    ):
        """
        Initialize River collector
        
        Args:
            prometheus_url: Prometheus server URL
            service_name: Name of service to collect metrics for
            batch_size: Number of data points per batch
            poll_interval: How often to poll Prometheus (seconds)
        """
        self.service_name = service_name
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        
        # Initialize Prometheus client
        self.prometheus = PrometheusClient(url=prometheus_url)
        
        # Data buffer
        self.buffer = []
        self.is_running = False
        
        # Statistics
        self.stats = {
            'total_collected': 0,
            'batches_emitted': 0,
            'start_time': None,
            'last_collection': None,
            'error_count': 0
        }
        
        # Callbacks
        self.on_data_callbacks = []
        self.on_batch_callbacks = []
        
        logger.info(f"✅ RiverCollector initialized for {self.service_name}")
    
    def collect_metrics(self, time_range: str = "1m") -> pd.DataFrame:
        """
        Collect metrics from Prometheus
        
        Args:
            time_range: Time range to collect (e.g., "1m", "5m", "1h")
        
        Returns:
            DataFrame with collected metrics
        """
        try:
            # Query for CPU metrics
            cpu_query = f'rate(container_cpu_usage_seconds_total{{service="{self.service_name}"}}[{time_range}])'
            cpu_df = self.prometheus.query_range(cpu_query, f"-{time_range}", "now", "15s")
            
            # Query for memory metrics
            memory_query = f'container_memory_working_set_bytes{{service="{self.service_name}"}}'
            memory_df = self.prometheus.query_range(memory_query, f"-{time_range}", "now", "15s")
            
            # Query for latency metrics
            latency_query = f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{self.service_name}"}}[{time_range}]))'
            latency_df = self.prometheus.query_range(latency_query, f"-{time_range}", "now", "15s")
            
            # Query for error rate
            error_query = f'rate(http_requests_total{{service="{self.service_name}", code="5xx"}}[{time_range}])'
            error_df = self.prometheus.query_range(error_query, f"-{time_range}", "now", "15s")
            
            # Merge all metrics
            metrics = {}
            
            if not cpu_df.empty:
                metrics['cpu'] = cpu_df[['timestamp', 'value']].rename(columns={'value': 'cpu_usage'})
            else:
                metrics['cpu'] = pd.DataFrame(columns=['timestamp', 'cpu_usage'])
            
            if not memory_df.empty:
                metrics['memory'] = memory_df[['timestamp', 'value']].rename(columns={'value': 'memory_usage'})
            else:
                metrics['memory'] = pd.DataFrame(columns=['timestamp', 'memory_usage'])
            
            if not latency_df.empty:
                metrics['latency'] = latency_df[['timestamp', 'value']].rename(columns={'value': 'request_latency'})
            else:
                metrics['latency'] = pd.DataFrame(columns=['timestamp', 'request_latency'])
            
            if not error_df.empty:
                metrics['error'] = error_df[['timestamp', 'value']].rename(columns={'value': 'error_rate'})
            else:
                metrics['error'] = pd.DataFrame(columns=['timestamp', 'error_rate'])
            
            # Merge all DataFrames on timestamp
            result = None
            
            for name, df in metrics.items():
                if df.empty:
                    continue
                
                if result is None:
                    result = df
                else:
                    # Merge on timestamp (outer join to keep all timestamps)
                    result = pd.merge(result, df, on='timestamp', how='outer')
            
            if result is None:
                return pd.DataFrame()
            
            # Fill missing values
            result = result.fillna(0)
            
            # Sort by timestamp
            result = result.sort_values('timestamp')
            
            self.stats['last_collection'] = datetime.now()
            
            logger.info(f"📊 Collected {len(result)} data points for {self.service_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error collecting metrics: {e}")
            self.stats['error_count'] += 1
            return pd.DataFrame()
    
    def collect_metrics_batch(self, time_range: str = "5m", step: str = "15s") -> List[Dict[str, Any]]:
        """
        Collect metrics and convert to River stream format
        
        Args:
            time_range: Time range to collect
            step: Step size for data points
        
        Returns:
            List of dictionaries in River format
        """
        df = self.collect_metrics(time_range)
        
        if df.empty:
            return []
        
        # Convert to River format
        river_data = []
        
        for _, row in df.iterrows():
            # Features
            features = {
                'cpu_usage': float(row.get('cpu_usage', 0)),
                'memory_usage': float(row.get('memory_usage', 0)),
                'request_latency': float(row.get('request_latency', 0)),
                'error_rate': float(row.get('error_rate', 0))
            }
            
            # Timestamp
            timestamp = row.get('timestamp', datetime.now())
            
            river_data.append({
                'features': features,
                'timestamp': timestamp,
                'service': self.service_name
            })
        
        return river_data
    
    def start_streaming(self):
        """
        Start streaming data from Prometheus
        (Runs asynchronously, yielding data points)
        """
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        logger.info(f"▶️ Starting River stream for {self.service_name}")
        
        while self.is_running:
            try:
                # Collect data
                data_points = self.collect_metrics_batch(
                    time_range=f"{self.poll_interval}s",
                    step="15s"
                )
                
                # Add to buffer
                self.buffer.extend(data_points)
                self.stats['total_collected'] += len(data_points)
                
                # Emit batch if buffer is full
                if len(self.buffer) >= self.batch_size:
                    self._emit_batch()
                
                # Call on_data callbacks for each point
                for point in data_points:
                    for callback in self.on_data_callbacks:
                        callback(point)
                
                # Wait before next poll
                asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"❌ Streaming error: {e}")
                self.stats['error_count'] += 1
                asyncio.sleep(5)  # Backoff on error
    
    def _emit_batch(self):
        """Emit a batch of data"""
        if not self.buffer:
            return
        
        batch = self.buffer[:self.batch_size]
        self.buffer = self.buffer[self.batch_size:]
        
        self.stats['batches_emitted'] += 1
        
        logger.info(f"📦 Emitted batch #{self.stats['batches_emitted']} with {len(batch)} points")
        
        # Call batch callbacks
        for callback in self.on_batch_callbacks:
            callback(batch)
    
    def stop_streaming(self):
        """Stop the streaming process"""
        self.is_running = False
        logger.info(f"⏹️ Stopped River stream for {self.service_name}")
    
    def get_dataframe(self, time_range: str = "5m") -> pd.DataFrame:
        """
        Get metrics as a DataFrame (convenience method)
        
        Args:
            time_range: Time range to collect
        
        Returns:
            DataFrame with metrics
        """
        return self.collect_metrics(time_range)
    
    def get_river_stream(self, time_range: str = "5m", shuffle: bool = False):
        """
        Get River stream iterator
        
        Args:
            time_range: Time range to collect
            shuffle: Whether to shuffle the data
        
        Returns:
            River stream iterator
        """
        data_points = self.collect_metrics_batch(time_range)
        
        if not data_points:
            return iter([])
        
        # Convert to River format (X, y)
        stream_data = []
        for point in data_points:
            X = point['features']
            y = 0  # No target (unsupervised)
            stream_data.append((X, y))
        
        if shuffle:
            import random
            random.shuffle(stream_data)
        
        return stream.iter_array(stream_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            'service': self.service_name,
            'is_running': self.is_running,
            'total_collected': self.stats['total_collected'],
            'batches_emitted': self.stats['batches_emitted'],
            'buffer_size': len(self.buffer),
            'error_count': self.stats['error_count'],
            'start_time': self.stats['start_time'],
            'last_collection': self.stats['last_collection']
        }
    
    def register_on_data(self, callback: Callable):
        """Register callback for each data point"""
        self.on_data_callbacks.append(callback)
    
    def register_on_batch(self, callback: Callable):
        """Register callback for each batch"""
        self.on_batch_callbacks.append(callback)