"""
Natural language to InfluxDB query translator for the ONS Data Platform.

This module provides functionality to translate natural language questions
about energy data into InfluxDB Flux and InfluxQL queries, with support
for parameter extraction and query generation logic.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class QueryLanguage(Enum):
    """Supported query languages."""
    FLUX = "flux"
    INFLUXQL = "influxql"


class QueryType(Enum):
    """Types of energy data queries."""
    GENERATION_TREND = "generation_trend"
    CONSUMPTION_PEAK = "consumption_peak"
    TRANSMISSION_LOSSES = "transmission_losses"
    CAPACITY_FACTOR = "capacity_factor"
    DEMAND_FORECAST = "demand_forecast"
    ENERGY_BALANCE = "energy_balance"
    REGIONAL_COMPARISON = "regional_comparison"
    SOURCE_BREAKDOWN = "source_breakdown"
    EFFICIENCY_ANALYSIS = "efficiency_analysis"
    LOAD_PROFILE = "load_profile"


@dataclass
class QueryParameters:
    """Parameters extracted from natural language query."""
    time_range: Dict[str, Any]
    regions: List[str]
    energy_sources: List[str]
    measurement_types: List[str]
    aggregation: str
    filters: Dict[str, Any]
    limit: Optional[int] = None
    group_by: List[str] = None


@dataclass
class QueryTemplate:
    """Template for generating InfluxDB queries."""
    query_type: QueryType
    flux_template: str
    influxql_template: str
    required_params: List[str]
    optional_params: List[str]
    description: str


class QueryTranslationError(Exception):
    """Raised when query translation fails."""
    pass


class QueryTranslator:
    """
    Natural language to InfluxDB query translator.
    
    Converts natural language questions about energy data into properly
    formatted InfluxDB Flux and InfluxQL queries with parameter extraction
    and validation.
    """
    
    def __init__(self):
        """Initialize the query translator with templates and patterns."""
        self.query_templates = self._initialize_query_templates()
        self.time_patterns = self._initialize_time_patterns()
        self.region_patterns = self._initialize_region_patterns()
        self.source_patterns = self._initialize_source_patterns()
        self.measurement_patterns = self._initialize_measurement_patterns()
        
        logger.info("QueryTranslator initialized with templates and patterns")
    
    def translate_query(
        self,
        question: str,
        language: QueryLanguage = QueryLanguage.FLUX,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Translate natural language question to InfluxDB query.
        
        Args:
            question: Natural language question about energy data
            language: Target query language (Flux or InfluxQL)
            context: Additional context for query generation
            
        Returns:
            Dictionary containing query, parameters, and metadata
            
        Raises:
            QueryTranslationError: If translation fails
        """
        try:
            # Validate input
            if not question or not question.strip():
                raise QueryTranslationError("Question cannot be empty")
            
            # Normalize the question
            normalized_question = self._normalize_question(question)
            
            # Identify query type
            query_type = self._identify_query_type(normalized_question)
            
            # Extract parameters
            parameters = self._extract_parameters(normalized_question, context)
            
            # Get query template
            template = self.query_templates.get(query_type)
            if not template:
                raise QueryTranslationError(f"No template found for query type: {query_type}")
            
            # Validate required parameters
            self._validate_parameters(template, parameters)
            
            # Generate query
            if language == QueryLanguage.FLUX:
                query = self._generate_flux_query(template, parameters)
            else:
                query = self._generate_influxql_query(template, parameters)
            
            return {
                'query': query,
                'query_type': query_type.value,
                'language': language.value,
                'parameters': parameters.__dict__,
                'template_description': template.description,
                'confidence_score': self._calculate_confidence_score(normalized_question, query_type)
            }
            
        except Exception as e:
            logger.error(f"Query translation failed: {e}")
            raise QueryTranslationError(f"Failed to translate query: {e}")
    
    def _normalize_question(self, question: str) -> str:
        """
        Normalize natural language question for processing.
        
        Args:
            question: Raw natural language question
            
        Returns:
            Normalized question string
        """
        # Convert to lowercase
        normalized = question.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove punctuation at the end
        normalized = re.sub(r'[?!.]+$', '', normalized)
        
        # Standardize common terms
        replacements = {
            'power generation': 'generation',
            'electricity generation': 'generation',
            'energy consumption': 'consumption',
            'power consumption': 'consumption',
            'electricity consumption': 'consumption',
            'transmission losses': 'losses',
            'grid losses': 'losses',
            'capacity factor': 'capacity_factor',
            'load factor': 'load_factor',
            'peak demand': 'peak_demand',
            'maximum demand': 'peak_demand',
            'renewable energy': 'renewable',
            'fossil fuel': 'fossil',
            'hydroelectric': 'hydro',
            'photovoltaic': 'solar',
            'wind power': 'wind'
        }
        
        for old_term, new_term in replacements.items():
            normalized = normalized.replace(old_term, new_term)
        
        return normalized
    
    def _identify_query_type(self, question: str) -> QueryType:
        """
        Identify the type of query based on keywords and patterns.
        
        Args:
            question: Normalized question string
            
        Returns:
            QueryType enum value
        """
        # Define keyword patterns for each query type
        patterns = {
            QueryType.GENERATION_TREND: [
                r'generation.*trend', r'trend.*generation', r'generation.*over time',
                r'generation.*history', r'generation.*pattern', r'how.*generation.*changed'
            ],
            QueryType.CONSUMPTION_PEAK: [
                r'peak.*consumption', r'maximum.*consumption', r'highest.*consumption',
                r'peak.*demand', r'maximum.*demand', r'consumption.*peak',
                r'consumption.*today', r'consumption.*trend'
            ],
            QueryType.TRANSMISSION_LOSSES: [
                r'transmission.*loss', r'grid.*loss', r'loss.*transmission',
                r'loss.*grid', r'energy.*loss', r'power.*loss'
            ],
            QueryType.CAPACITY_FACTOR: [
                r'capacity.*factor', r'capacity.*utilization', r'plant.*efficiency',
                r'utilization.*rate', r'availability.*factor'
            ],
            QueryType.REGIONAL_COMPARISON: [
                r'compare.*region', r'regional.*comparison', r'region.*vs',
                r'between.*region', r'across.*region'
            ],
            QueryType.SOURCE_BREAKDOWN: [
                r'by.*source', r'source.*breakdown', r'energy.*source',
                r'renewable.*vs', r'fossil.*vs', r'mix.*energy'
            ],
            QueryType.EFFICIENCY_ANALYSIS: [
                r'efficiency', r'performance', r'optimization',
                r'how.*efficient', r'efficiency.*analysis'
            ],
            QueryType.LOAD_PROFILE: [
                r'load.*profile', r'demand.*profile', r'consumption.*profile',
                r'daily.*pattern', r'hourly.*pattern', r'load.*curve'
            ],
            QueryType.ENERGY_BALANCE: [
                r'energy.*balance', r'supply.*demand', r'generation.*consumption',
                r'balance.*energy', r'supply.*vs.*demand'
            ]
        }
        
        # Add consumption-specific patterns that should take precedence
        consumption_indicators = [
            r'consumption', r'demand', r'load'
        ]
        
        # Check for consumption indicators first
        has_consumption = any(re.search(pattern, question) for pattern in consumption_indicators)
        
        # Special handling for consumption queries
        if has_consumption:
            # Check if it's a comparison (regional or sectoral)
            if re.search(r'compare.*consumption|consumption.*between|between.*consumption', question):
                return QueryType.REGIONAL_COMPARISON
            # Check if it's specifically about peak/maximum
            elif re.search(r'peak|maximum|highest|max', question):
                return QueryType.CONSUMPTION_PEAK
            # Check if it's about trends
            elif re.search(r'trend|over time|history|pattern', question):
                return QueryType.LOAD_PROFILE
        
        # Score each query type based on pattern matches
        scores = {}
        for query_type, type_patterns in patterns.items():
            score = 0
            for pattern in type_patterns:
                if re.search(pattern, question):
                    score += 1
            scores[query_type] = score
        
        # Return the query type with the highest score
        if scores and max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        # Default to generation trend if no specific pattern matches
        return QueryType.GENERATION_TREND
    
    def _extract_parameters(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryParameters:
        """
        Extract query parameters from natural language question.
        
        Args:
            question: Normalized question string
            context: Additional context for parameter extraction
            
        Returns:
            QueryParameters object with extracted parameters
        """
        # Extract time range
        time_range = self._extract_time_range(question, context)
        
        # Extract regions
        regions = self._extract_regions(question, context)
        
        # Extract energy sources
        energy_sources = self._extract_energy_sources(question, context)
        
        # Extract measurement types
        measurement_types = self._extract_measurement_types(question, context)
        
        # Extract aggregation type
        aggregation = self._extract_aggregation(question, context)
        
        # Extract filters
        filters = self._extract_filters(question, context)
        
        # Extract limit
        limit = self._extract_limit(question, context)
        
        # Extract group by
        group_by = self._extract_group_by(question, context)
        
        return QueryParameters(
            time_range=time_range,
            regions=regions,
            energy_sources=energy_sources,
            measurement_types=measurement_types,
            aggregation=aggregation,
            filters=filters,
            limit=limit,
            group_by=group_by
        )
    
    def _extract_time_range(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract time range from question."""
        now = datetime.now(timezone.utc)
        
        # Check for specific time patterns
        for pattern, delta_func in self.time_patterns.items():
            if re.search(pattern, question):
                start_time, end_time = delta_func(now)
                return {
                    'start': start_time.isoformat(),
                    'stop': end_time.isoformat(),
                    'relative': True
                }
        
        # Check for absolute dates
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        dates = re.findall(date_pattern, question)
        if len(dates) >= 2:
            return {
                'start': f"{dates[0]}T00:00:00Z",
                'stop': f"{dates[1]}T23:59:59Z",
                'relative': False
            }
        elif len(dates) == 1:
            date = datetime.fromisoformat(dates[0])
            return {
                'start': f"{dates[0]}T00:00:00Z",
                'stop': (date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
                'relative': False
            }
        
        # Default to last 30 days
        start_time = now - timedelta(days=30)
        return {
            'start': start_time.isoformat(),
            'stop': now.isoformat(),
            'relative': True
        }
    
    def _extract_regions(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Extract regions from question."""
        regions = []
        
        for pattern, region_list in self.region_patterns.items():
            if re.search(pattern, question):
                regions.extend(region_list)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(regions))
    
    def _extract_energy_sources(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Extract energy sources from question."""
        sources = []
        
        for pattern, source_list in self.source_patterns.items():
            if re.search(pattern, question):
                sources.extend(source_list)
        
        return list(dict.fromkeys(sources))
    
    def _extract_measurement_types(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Extract measurement types from question."""
        measurements = []
        
        for pattern, measurement_list in self.measurement_patterns.items():
            if re.search(pattern, question):
                measurements.extend(measurement_list)
        
        return list(dict.fromkeys(measurements))
    
    def _extract_aggregation(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Extract aggregation type from question."""
        aggregation_patterns = {
            r'average|avg|mean': 'mean',
            r'sum|total': 'sum',
            r'maximum|max|peak|highest': 'max',
            r'minimum|min|lowest': 'min',
            r'count': 'count',
            r'median': 'median',
            r'standard deviation|stddev': 'stddev'
        }
        
        for pattern, agg_type in aggregation_patterns.items():
            if re.search(pattern, question):
                return agg_type
        
        return 'mean'  # Default aggregation
    
    def _extract_filters(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract additional filters from question."""
        filters = {}
        
        # Extract quality filters
        if re.search(r'high.*quality|good.*quality|valid.*data', question):
            filters['quality_flag'] = 'good'
        elif re.search(r'low.*quality|poor.*quality|invalid.*data', question):
            filters['quality_flag'] = 'poor'
        
        # Extract capacity filters - improved pattern
        capacity_match = re.search(r'capacity.*?(?:above|over|greater than|>)\s*(\d+)', question)
        if capacity_match:
            filters['min_capacity'] = int(capacity_match.group(1))
        
        # Extract efficiency filters - improved pattern
        efficiency_match = re.search(r'efficiency.*?(?:above|over|greater than|>)\s*(\d+)', question)
        if efficiency_match:
            filters['min_efficiency'] = float(efficiency_match.group(1)) / 100
        
        return filters
    
    def _extract_limit(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Extract result limit from question."""
        limit_patterns = [
            r'top\s+(\d+)',
            r'first\s+(\d+)',
            r'limit\s+(\d+)',
            r'(\d+)\s+results?'
        ]
        
        for pattern in limit_patterns:
            match = re.search(pattern, question)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_group_by(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Extract group by fields from question."""
        group_by = []
        
        group_patterns = {
            r'by.*region|per.*region|each.*region': ['region'],
            r'by.*source|per.*source|each.*source': ['energy_source'],
            r'by.*hour|hourly|per.*hour': ['hour'],
            r'by.*day|daily|per.*day': ['day'],
            r'by.*month|monthly|per.*month': ['month'],
            r'by.*year|yearly|annually|per.*year': ['year']
        }
        
        for pattern, fields in group_patterns.items():
            if re.search(pattern, question):
                group_by.extend(fields)
        
        return list(dict.fromkeys(group_by))
    
    def _generate_flux_query(
        self,
        template: QueryTemplate,
        parameters: QueryParameters
    ) -> str:
        """
        Generate Flux query from template and parameters.
        
        Args:
            template: Query template
            parameters: Extracted parameters
            
        Returns:
            Generated Flux query string
        """
        # Prepare template variables
        template_vars = {
            'start_time': parameters.time_range['start'],
            'stop_time': parameters.time_range['stop'],
            'aggregation': parameters.aggregation,
            'bucket': 'energy_data'  # Default bucket
        }
        
        # Add region filters
        if parameters.regions:
            region_filter = ' or '.join([f'r["region"] == "{region}"' for region in parameters.regions])
            template_vars['region_filter'] = f'|> filter(fn: (r) => {region_filter})'
        else:
            template_vars['region_filter'] = ''
        
        # Add energy source filters
        if parameters.energy_sources:
            source_filter = ' or '.join([f'r["energy_source"] == "{source}"' for source in parameters.energy_sources])
            template_vars['source_filter'] = f'|> filter(fn: (r) => {source_filter})'
        else:
            template_vars['source_filter'] = ''
        
        # Add measurement type filters
        if parameters.measurement_types:
            measurement_filter = ' or '.join([f'r["_measurement"] == "{measurement}"' for measurement in parameters.measurement_types])
            template_vars['measurement_filter'] = f'|> filter(fn: (r) => {measurement_filter})'
        else:
            template_vars['measurement_filter'] = ''
        
        # Add group by
        if parameters.group_by:
            group_by_fields = ', '.join([f'"{field}"' for field in parameters.group_by])
            template_vars['group_by'] = f'|> group(columns: [{group_by_fields}])'
        else:
            template_vars['group_by'] = ''
        
        # Add limit
        if parameters.limit:
            template_vars['limit'] = f'|> limit(n: {parameters.limit})'
        else:
            template_vars['limit'] = ''
        
        # Add additional filters
        additional_filters = []
        for key, value in parameters.filters.items():
            if key == 'quality_flag':
                additional_filters.append(f'|> filter(fn: (r) => r["quality_flag"] == "{value}")')
            elif key == 'min_capacity':
                additional_filters.append(f'|> filter(fn: (r) => r["capacity_mw"] >= {value})')
            elif key == 'min_efficiency':
                additional_filters.append(f'|> filter(fn: (r) => r["efficiency"] >= {value})')
        
        template_vars['additional_filters'] = '\n  '.join(additional_filters)
        
        # Generate query from template
        try:
            query = template.flux_template.format(**template_vars)
            return query.strip()
        except KeyError as e:
            raise QueryTranslationError(f"Missing template variable: {e}")
    
    def _generate_influxql_query(
        self,
        template: QueryTemplate,
        parameters: QueryParameters
    ) -> str:
        """
        Generate InfluxQL query from template and parameters.
        
        Args:
            template: Query template
            parameters: Extracted parameters
            
        Returns:
            Generated InfluxQL query string
        """
        # Prepare template variables
        template_vars = {
            'start_time': parameters.time_range['start'],
            'stop_time': parameters.time_range['stop'],
            'aggregation': parameters.aggregation.upper(),
            'database': 'energy_data'  # Default database
        }
        
        # Add WHERE conditions
        where_conditions = [f"time >= '{parameters.time_range['start']}'", f"time <= '{parameters.time_range['stop']}'"]
        
        if parameters.regions:
            region_condition = ' OR '.join([f"region = '{region}'" for region in parameters.regions])
            where_conditions.append(f"({region_condition})")
        
        if parameters.energy_sources:
            source_condition = ' OR '.join([f"energy_source = '{source}'" for source in parameters.energy_sources])
            where_conditions.append(f"({source_condition})")
        
        # Add additional filters
        for key, value in parameters.filters.items():
            if key == 'quality_flag':
                where_conditions.append(f"quality_flag = '{value}'")
            elif key == 'min_capacity':
                where_conditions.append(f"capacity_mw >= {value}")
            elif key == 'min_efficiency':
                where_conditions.append(f"efficiency >= {value}")
        
        template_vars['where_clause'] = ' AND '.join(where_conditions)
        
        # Add GROUP BY
        if parameters.group_by:
            template_vars['group_by'] = f"GROUP BY {', '.join(parameters.group_by)}"
        else:
            template_vars['group_by'] = ''
        
        # Add LIMIT
        if parameters.limit:
            template_vars['limit'] = f'LIMIT {parameters.limit}'
        else:
            template_vars['limit'] = ''
        
        # Generate query from template
        try:
            query = template.influxql_template.format(**template_vars)
            return query.strip()
        except KeyError as e:
            raise QueryTranslationError(f"Missing template variable: {e}")
    
    def _validate_parameters(
        self,
        template: QueryTemplate,
        parameters: QueryParameters
    ) -> None:
        """
        Validate that required parameters are present.
        
        Args:
            template: Query template
            parameters: Extracted parameters
            
        Raises:
            QueryTranslationError: If required parameters are missing
        """
        missing_params = []
        
        for param in template.required_params:
            if param == 'time_range' and not parameters.time_range:
                missing_params.append(param)
            elif param == 'regions' and not parameters.regions:
                missing_params.append(param)
            elif param == 'energy_sources' and not parameters.energy_sources:
                missing_params.append(param)
            elif param == 'measurement_types' and not parameters.measurement_types:
                missing_params.append(param)
        
        if missing_params:
            raise QueryTranslationError(f"Missing required parameters: {missing_params}")
    
    def _calculate_confidence_score(
        self,
        question: str,
        query_type: QueryType
    ) -> float:
        """
        Calculate confidence score for query translation.
        
        Args:
            question: Normalized question
            query_type: Identified query type
            
        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence based on query type identification
        base_confidence = 0.7
        
        # Boost confidence for specific keywords
        confidence_boosters = {
            'generation': 0.1,
            'consumption': 0.1,
            'transmission': 0.1,
            'region': 0.05,
            'source': 0.05,
            'trend': 0.05,
            'peak': 0.05,
            'efficiency': 0.05
        }
        
        confidence = base_confidence
        for keyword, boost in confidence_boosters.items():
            if keyword in question:
                confidence += boost
        
        return min(confidence, 1.0)
    
    def _initialize_query_templates(self) -> Dict[QueryType, QueryTemplate]:
        """Initialize query templates for different query types."""
        templates = {}
        
        # Generation trend template
        templates[QueryType.GENERATION_TREND] = QueryTemplate(
            query_type=QueryType.GENERATION_TREND,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "generation_data")
  {region_filter}
  {source_filter}
  {measurement_filter}
  {additional_filters}
  |> aggregateWindow(every: 1h, fn: {aggregation})
  {group_by}
  |> sort(columns: ["_time"])
  {limit}
            '''.strip(),
            influxql_template='''
SELECT {aggregation}(power_mw) FROM generation_data
WHERE {where_clause}
{group_by}
ORDER BY time
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['regions', 'energy_sources', 'aggregation'],
            description="Analyze power generation trends over time"
        )
        
        # Consumption peak template
        templates[QueryType.CONSUMPTION_PEAK] = QueryTemplate(
            query_type=QueryType.CONSUMPTION_PEAK,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "consumption_data")
  |> filter(fn: (r) => r["_field"] == "demand_mw")
  {region_filter}
  {additional_filters}
  |> max()
  {group_by}
  {limit}
            '''.strip(),
            influxql_template='''
SELECT MAX(demand_mw) FROM consumption_data
WHERE {where_clause}
{group_by}
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['regions'],
            description="Find peak consumption/demand values"
        )
        
        # Transmission losses template
        templates[QueryType.TRANSMISSION_LOSSES] = QueryTemplate(
            query_type=QueryType.TRANSMISSION_LOSSES,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "transmission_data")
  |> filter(fn: (r) => r["_field"] == "losses_mwh")
  {region_filter}
  {additional_filters}
  |> sum()
  {group_by}
  {limit}
            '''.strip(),
            influxql_template='''
SELECT SUM(losses_mwh) FROM transmission_data
WHERE {where_clause}
{group_by}
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['regions'],
            description="Calculate transmission losses"
        )
        
        # Regional comparison template
        templates[QueryType.REGIONAL_COMPARISON] = QueryTemplate(
            query_type=QueryType.REGIONAL_COMPARISON,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "generation_data")
  {source_filter}
  {measurement_filter}
  {additional_filters}
  |> group(columns: ["region"])
  |> {aggregation}()
  |> sort(columns: ["_value"], desc: true)
  {limit}
            '''.strip(),
            influxql_template='''
SELECT {aggregation}(power_mw) FROM generation_data
WHERE {where_clause}
GROUP BY region
ORDER BY 1 DESC
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['energy_sources', 'aggregation'],
            description="Compare energy metrics across regions"
        )
        
        # Source breakdown template
        templates[QueryType.SOURCE_BREAKDOWN] = QueryTemplate(
            query_type=QueryType.SOURCE_BREAKDOWN,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "generation_data")
  {region_filter}
  {additional_filters}
  |> group(columns: ["energy_source"])
  |> {aggregation}()
  |> sort(columns: ["_value"], desc: true)
  {limit}
            '''.strip(),
            influxql_template='''
SELECT {aggregation}(power_mw) FROM generation_data
WHERE {where_clause}
GROUP BY energy_source
ORDER BY 1 DESC
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['regions', 'aggregation'],
            description="Break down energy generation by source type"
        )
        
        # Load profile template
        templates[QueryType.LOAD_PROFILE] = QueryTemplate(
            query_type=QueryType.LOAD_PROFILE,
            flux_template='''
from(bucket: "{bucket}")
  |> range(start: {start_time}, stop: {stop_time})
  |> filter(fn: (r) => r["_measurement"] == "consumption_data")
  |> filter(fn: (r) => r["_field"] == "demand_mw")
  {region_filter}
  {additional_filters}
  |> aggregateWindow(every: 1h, fn: {aggregation})
  {group_by}
  |> sort(columns: ["_time"])
  {limit}
            '''.strip(),
            influxql_template='''
SELECT {aggregation}(demand_mw) FROM consumption_data
WHERE {where_clause}
{group_by}
ORDER BY time
{limit}
            '''.strip(),
            required_params=['time_range'],
            optional_params=['regions', 'aggregation'],
            description="Analyze consumption load profiles and patterns"
        )
        
        return templates
    
    def _initialize_time_patterns(self) -> Dict[str, callable]:
        """Initialize time range extraction patterns."""
        def last_hour(now):
            return now - timedelta(hours=1), now
        
        def last_day(now):
            return now - timedelta(days=1), now
        
        def last_week(now):
            return now - timedelta(weeks=1), now
        
        def last_month(now):
            return now - timedelta(days=30), now
        
        def last_year(now):
            return now - timedelta(days=365), now
        
        def today(now):
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        
        def yesterday(now):
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1) - timedelta(microseconds=1)
            return yesterday_start, yesterday_end
        
        return {
            r'last\s+hour|past\s+hour': last_hour,
            r'last\s+day|past\s+day|yesterday': last_day,
            r'last\s+week|past\s+week': last_week,
            r'last\s+month|past\s+month': last_month,
            r'last\s+year|past\s+year': last_year,
            r'today|this\s+day': today,
            r'yesterday': yesterday
        }
    
    def _initialize_region_patterns(self) -> Dict[str, List[str]]:
        """Initialize region extraction patterns."""
        return {
            r'southeast|south.*east': ['southeast'],
            r'northeast|north.*east': ['northeast'],
            r'south|southern': ['south'],
            r'north|northern': ['north'],
            r'central': ['central'],
            r'all.*region|every.*region': ['southeast', 'northeast', 'south', 'north', 'central']
        }
    
    def _initialize_source_patterns(self) -> Dict[str, List[str]]:
        """Initialize energy source extraction patterns."""
        return {
            r'hydro|hydroelectric': ['hydro'],
            r'solar|photovoltaic|pv': ['solar'],
            r'wind': ['wind'],
            r'thermal|coal|gas|fossil': ['thermal'],
            r'nuclear': ['nuclear'],
            r'renewable': ['hydro', 'solar', 'wind'],
            r'fossil|non.*renewable': ['thermal'],
            r'all.*source|every.*source': ['hydro', 'solar', 'wind', 'thermal', 'nuclear']
        }
    
    def _initialize_measurement_patterns(self) -> Dict[str, List[str]]:
        """Initialize measurement type extraction patterns."""
        return {
            r'generation|power.*generation': ['generation_data'],
            r'consumption|demand': ['consumption_data'],
            r'transmission|grid': ['transmission_data'],
            r'all.*data|every.*measurement': ['generation_data', 'consumption_data', 'transmission_data']
        }


def create_query_translator() -> QueryTranslator:
    """
    Factory function to create a QueryTranslator instance.
    
    Returns:
        QueryTranslator instance
    """
    return QueryTranslator()


def translate_natural_language_query(
    question: str,
    language: QueryLanguage = QueryLanguage.FLUX,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to translate natural language to InfluxDB query.
    
    Args:
        question: Natural language question about energy data
        language: Target query language (Flux or InfluxQL)
        context: Additional context for query generation
        
    Returns:
        Dictionary containing query, parameters, and metadata
        
    Raises:
        QueryTranslationError: If translation fails
    """
    translator = create_query_translator()
    return translator.translate_query(question, language, context)