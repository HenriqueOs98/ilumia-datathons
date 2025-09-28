"""
Unit tests for query translator.

Tests the QueryTranslator class for converting natural language questions
to InfluxDB Flux and InfluxQL queries.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.shared_utils.query_translator import (
    QueryTranslator,
    QueryLanguage,
    QueryType,
    QueryParameters,
    QueryTemplate,
    QueryTranslationError
)


class TestQueryTranslator:
    """Test cases for QueryTranslator class."""
    
    @pytest.fixture
    def translator(self):
        """Create QueryTranslator instance for testing."""
        return QueryTranslator()
    
    def test_init(self, translator):
        """Test translator initialization."""
        assert translator.query_templates is not None
        assert translator.time_patterns is not None
        assert translator.region_patterns is not None
        assert translator.source_patterns is not None
        assert translator.measurement_patterns is not None
    
    def test_normalize_question(self, translator):
        """Test question normalization."""
        test_cases = [
            ("What is the power generation trend?", "what is the generation trend"),
            ("Show me electricity consumption data!", "show me consumption data"),
            ("  Multiple   spaces   here  ", "multiple spaces here"),
            ("Power generation in the last week?", "generation in the last week"),
            ("Renewable energy vs fossil fuel", "renewable vs fossil")
        ]
        
        for input_question, expected in test_cases:
            result = translator._normalize_question(input_question)
            assert result == expected
    
    def test_identify_query_type_generation_trend(self, translator):
        """Test identification of generation trend queries."""
        test_questions = [
            "show me generation trend over time",
            "how has generation changed in the last month",
            "generation pattern for hydro plants",
            "generation history for southeast region"
        ]
        
        for question in test_questions:
            normalized = translator._normalize_question(question)
            query_type = translator._identify_query_type(normalized)
            assert query_type == QueryType.GENERATION_TREND
    
    def test_identify_query_type_consumption_peak(self, translator):
        """Test identification of consumption peak queries."""
        test_questions = [
            "what is the peak consumption today",
            "maximum demand in the last hour",
            "highest consumption this week",
            "peak demand for industrial sector"
        ]
        
        for question in test_questions:
            normalized = translator._normalize_question(question)
            query_type = translator._identify_query_type(normalized)
            assert query_type == QueryType.CONSUMPTION_PEAK
    
    def test_identify_query_type_transmission_losses(self, translator):
        """Test identification of transmission loss queries."""
        test_questions = [
            "show me transmission losses",
            "grid losses in the southeast",
            "energy losses in transmission lines",
            "power losses for high voltage lines"
        ]
        
        for question in test_questions:
            normalized = translator._normalize_question(question)
            query_type = translator._identify_query_type(normalized)
            assert query_type == QueryType.TRANSMISSION_LOSSES
    
    def test_identify_query_type_regional_comparison(self, translator):
        """Test identification of regional comparison queries."""
        test_questions = [
            "compare consumption between regions",
            "regional comparison of generation",
            "consumption across different regions",
            "generation in southeast vs northeast"
        ]
        
        for question in test_questions:
            normalized = translator._normalize_question(question)
            query_type = translator._identify_query_type(normalized)
            assert query_type == QueryType.REGIONAL_COMPARISON
    
    def test_identify_query_type_source_breakdown(self, translator):
        """Test identification of source breakdown queries."""
        test_questions = [
            "generation by energy source",
            "renewable vs fossil fuel generation",
            "energy source breakdown",
            "hydro vs wind generation"
        ]
        
        for question in test_questions:
            normalized = translator._normalize_question(question)
            query_type = translator._identify_query_type(normalized)
            assert query_type == QueryType.SOURCE_BREAKDOWN
    
    def test_extract_time_range_relative(self, translator):
        """Test extraction of relative time ranges."""
        test_cases = [
            ("data from last hour", 1),  # hours
            ("show me last 24 hours", 24),
            ("data from last week", 7 * 24),
            ("last month data", 30 * 24),
            ("data from last year", 365 * 24)
        ]
        
        for question, expected_hours in test_cases:
            time_range = translator._extract_time_range(question)
            
            assert time_range['relative'] is True
            start_time = datetime.fromisoformat(time_range['start'].replace('Z', '+00:00'))
            stop_time = datetime.fromisoformat(time_range['stop'].replace('Z', '+00:00'))
            
            # Check that the time range is approximately correct
            duration = stop_time - start_time
            expected_duration = timedelta(hours=expected_hours)
            
            # Allow some tolerance for test execution time
            assert abs(duration.total_seconds() - expected_duration.total_seconds()) < 60
    
    def test_extract_time_range_absolute(self, translator):
        """Test extraction of absolute time ranges."""
        question = "data from 2024-01-01 to 2024-01-31"
        time_range = translator._extract_time_range(question)
        
        assert time_range['relative'] is False
        assert time_range['start'] == "2024-01-01T00:00:00Z"
        assert time_range['stop'] == "2024-01-31T23:59:59Z"
    
    def test_extract_time_range_single_date(self, translator):
        """Test extraction of single date."""
        question = "data for 2024-01-15"
        time_range = translator._extract_time_range(question)
        
        assert time_range['relative'] is False
        assert time_range['start'] == "2024-01-15T00:00:00Z"
        assert time_range['stop'] == "2024-01-16T00:00:00Z"
    
    def test_extract_regions(self, translator):
        """Test extraction of regions from questions."""
        test_cases = [
            ("generation in southeast region", ['southeast']),
            ("data for northeast and south", ['northeast', 'south']),
            ("all regions data", ['southeast', 'northeast', 'south', 'north', 'central']),
            ("no region mentioned", [])
        ]
        
        for question, expected_regions in test_cases:
            regions = translator._extract_regions(question)
            
            # Check that expected regions are present (order may vary)
            for region in expected_regions:
                assert region in regions or any(region in r for r in regions)
    
    def test_extract_energy_sources(self, translator):
        """Test extraction of energy sources from questions."""
        test_cases = [
            ("hydro generation data", ['hydro']),
            ("wind and solar generation", ['wind', 'solar']),
            ("renewable energy sources", ['hydro', 'wind', 'solar']),
            ("fossil fuel generation", ['coal', 'gas', 'oil']),
            ("no source mentioned", [])
        ]
        
        for question, expected_sources in test_cases:
            sources = translator._extract_energy_sources(question)
            
            # Check that at least some expected sources are present
            if expected_sources:
                assert any(source in sources for source in expected_sources)
            else:
                assert sources == []
    
    def test_extract_aggregation(self, translator):
        """Test extraction of aggregation types."""
        test_cases = [
            ("average generation", "mean"),
            ("total consumption", "sum"),
            ("maximum demand", "max"),
            ("minimum losses", "min"),
            ("count of records", "count"),
            ("median value", "median"),
            ("no aggregation mentioned", "mean")  # default
        ]
        
        for question, expected_agg in test_cases:
            aggregation = translator._extract_aggregation(question)
            assert aggregation == expected_agg
    
    def test_extract_filters(self, translator):
        """Test extraction of filters from questions."""
        test_cases = [
            ("high quality data only", {'quality_flag': 'good'}),
            ("plants with capacity above 1000", {'min_capacity': 1000}),
            ("efficiency greater than 80", {'min_efficiency': 0.8}),
            ("no filters mentioned", {})
        ]
        
        for question, expected_filters in test_cases:
            filters = translator._extract_filters(question)
            
            for key, value in expected_filters.items():
                assert key in filters
                assert filters[key] == value
    
    def test_extract_limit(self, translator):
        """Test extraction of result limits."""
        test_cases = [
            ("top 10 plants", 10),
            ("first 5 results", 5),
            ("limit to 20 records", 20),
            ("show 100 results", 100),
            ("no limit mentioned", None)
        ]
        
        for question, expected_limit in test_cases:
            limit = translator._extract_limit(question)
            assert limit == expected_limit
    
    def test_extract_group_by(self, translator):
        """Test extraction of group by fields."""
        test_cases = [
            ("data by region", ['region']),
            ("breakdown by energy source", ['energy_source']),
            ("hourly data", ['hour']),
            ("daily breakdown", ['day']),
            ("monthly summary", ['month']),
            ("yearly data", ['year']),
            ("by region and source", ['region', 'energy_source']),
            ("no grouping mentioned", [])
        ]
        
        for question, expected_groups in test_cases:
            group_by = translator._extract_group_by(question)
            
            for group in expected_groups:
                assert group in group_by
    
    def test_translate_query_flux_generation_trend(self, translator):
        """Test translation to Flux query for generation trend."""
        question = "show me generation trend in southeast for last week"
        
        result = translator.translate_query(question, QueryLanguage.FLUX)
        
        assert result['query_type'] == 'generation_trend'
        assert result['language'] == 'flux'
        assert 'from(bucket:' in result['query']
        assert 'generation_data' in result['query']
        assert 'southeast' in result['query']
        assert result['confidence_score'] > 0.7
    
    def test_translate_query_influxql_consumption_peak(self, translator):
        """Test translation to InfluxQL query for consumption peak."""
        question = "what is the maximum consumption in northeast region"
        
        result = translator.translate_query(question, QueryLanguage.INFLUXQL)
        
        assert result['query_type'] == 'consumption_peak'
        assert result['language'] == 'influxql'
        assert 'SELECT MAX(' in result['query']
        assert 'consumption_data' in result['query']
        assert 'northeast' in result['query']
    
    def test_translate_query_with_context(self, translator):
        """Test query translation with additional context."""
        question = "show me recent data"
        context = {
            'default_region': 'southeast',
            'default_time_range': 'last_24_hours',
            'preferred_sources': ['hydro', 'wind']
        }
        
        result = translator.translate_query(question, context=context)
        
        assert result is not None
        assert 'query' in result
    
    def test_translate_query_empty_question(self, translator):
        """Test translation with empty question."""
        with pytest.raises(QueryTranslationError, match="Question cannot be empty"):
            translator.translate_query("")
    
    def test_translate_query_invalid_template(self, translator):
        """Test translation when template is missing variables."""
        question = "show me generation data"
        
        # Mock a template with missing variables
        with patch.object(translator, 'query_templates') as mock_templates:
            mock_template = QueryTemplate(
                query_type=QueryType.GENERATION_TREND,
                flux_template="from(bucket: {missing_var})",  # Missing variable
                influxql_template="SELECT * FROM test",
                required_params=[],
                optional_params=[],
                description="Test template"
            )
            mock_templates.get.return_value = mock_template
            
            with pytest.raises(QueryTranslationError, match="Missing template variable"):
                translator.translate_query(question)
    
    def test_generate_flux_query_with_all_filters(self, translator):
        """Test Flux query generation with all types of filters."""
        template = translator.query_templates[QueryType.GENERATION_TREND]
        
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-01T23:59:59Z'},
            regions=['southeast', 'northeast'],
            energy_sources=['hydro', 'wind'],
            measurement_types=['power_mw'],
            aggregation='mean',
            filters={'quality_flag': 'good', 'min_capacity': 1000},
            limit=10,
            group_by=['region']
        )
        
        query = translator._generate_flux_query(template, parameters)
        
        assert 'from(bucket: "energy_data")' in query
        assert 'range(start: 2024-01-01T00:00:00Z, stop: 2024-01-01T23:59:59Z)' in query
        assert 'r["region"] == "southeast"' in query
        assert 'r["region"] == "northeast"' in query
        assert 'r["energy_source"] == "hydro"' in query
        assert 'r["energy_source"] == "wind"' in query
        assert 'aggregateWindow(every: 1h, fn: mean)' in query
        assert 'limit(n: 10)' in query
        assert 'group(columns: ["region"])' in query
    
    def test_generate_influxql_query_with_filters(self, translator):
        """Test InfluxQL query generation with filters."""
        template = translator.query_templates[QueryType.CONSUMPTION_PEAK]
        
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-01T23:59:59Z'},
            regions=['southeast'],
            energy_sources=[],
            measurement_types=[],
            aggregation='max',
            filters={'quality_flag': 'good'},
            limit=5,
            group_by=['region']
        )
        
        query = translator._generate_influxql_query(template, parameters)
        
        assert 'SELECT MAX(' in query
        assert 'consumption_data' in query
        assert "time >= '2024-01-01T00:00:00Z'" in query
        assert "time <= '2024-01-01T23:59:59Z'" in query
        assert "region = 'southeast'" in query
        assert "quality_flag = 'good'" in query
        assert 'LIMIT 5' in query
        assert 'GROUP BY' in query
    
    def test_validate_parameters_missing_required(self, translator):
        """Test parameter validation with missing required parameters."""
        template = QueryTemplate(
            query_type=QueryType.GENERATION_TREND,
            flux_template="test",
            influxql_template="test",
            required_params=['time_range', 'regions'],
            optional_params=[],
            description="Test"
        )
        
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-01T23:59:59Z'},
            regions=[],  # Missing required regions
            energy_sources=[],
            measurement_types=[],
            aggregation='mean',
            filters={},
            limit=None,
            group_by=[]
        )
        
        with pytest.raises(QueryTranslationError, match="Missing required parameters"):
            translator._validate_parameters(template, parameters)
    
    def test_calculate_confidence_score(self, translator):
        """Test confidence score calculation."""
        test_cases = [
            ("generation trend in southeast", QueryType.GENERATION_TREND, 0.85),
            ("show data", QueryType.GENERATION_TREND, 0.7),  # Base confidence
            ("consumption peak efficiency", QueryType.CONSUMPTION_PEAK, 0.9)  # Multiple keywords
        ]
        
        for question, query_type, min_expected in test_cases:
            score = translator._calculate_confidence_score(question, query_type)
            assert score >= min_expected
            assert score <= 1.0
    
    def test_complex_query_translation(self, translator):
        """Test translation of complex query with multiple parameters."""
        question = """
        Show me the average hydro and wind generation trend in southeast and northeast regions
        for the last 30 days, grouped by region and energy source, with high quality data only,
        limited to top 20 results
        """
        
        result = translator.translate_query(question, QueryLanguage.FLUX)
        
        assert result['query_type'] in ['generation_trend', 'regional_comparison', 'source_breakdown']
        assert result['language'] == 'flux'
        assert 'hydro' in result['parameters']['energy_sources'] or 'wind' in result['parameters']['energy_sources']
        assert 'southeast' in result['parameters']['regions'] or 'northeast' in result['parameters']['regions']
        assert result['parameters']['aggregation'] == 'mean'
        assert result['parameters']['filters'].get('quality_flag') == 'good'
        assert result['parameters']['limit'] == 20


class TestQueryParameters:
    """Test QueryParameters dataclass."""
    
    def test_query_parameters_creation(self):
        """Test QueryParameters creation with all fields."""
        params = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-01T23:59:59Z'},
            regions=['southeast'],
            energy_sources=['hydro'],
            measurement_types=['power_mw'],
            aggregation='mean',
            filters={'quality_flag': 'good'},
            limit=10,
            group_by=['region']
        )
        
        assert params.time_range['start'] == '2024-01-01T00:00:00Z'
        assert params.regions == ['southeast']
        assert params.energy_sources == ['hydro']
        assert params.aggregation == 'mean'
        assert params.limit == 10


class TestQueryTemplate:
    """Test QueryTemplate dataclass."""
    
    def test_query_template_creation(self):
        """Test QueryTemplate creation."""
        template = QueryTemplate(
            query_type=QueryType.GENERATION_TREND,
            flux_template="from(bucket: {bucket})",
            influxql_template="SELECT * FROM {table}",
            required_params=['time_range'],
            optional_params=['regions'],
            description="Test template"
        )
        
        assert template.query_type == QueryType.GENERATION_TREND
        assert template.flux_template == "from(bucket: {bucket})"
        assert template.required_params == ['time_range']
        assert template.description == "Test template"


class TestQueryTranslatorEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def translator(self):
        """Create QueryTranslator instance for testing."""
        return QueryTranslator()
    
    def test_ambiguous_query_handling(self, translator):
        """Test handling of ambiguous queries."""
        ambiguous_questions = [
            "show me data",
            "what happened yesterday",
            "give me information",
            "tell me about energy"
        ]
        
        for question in ambiguous_questions:
            # Should not raise an error, should default to some query type
            result = translator.translate_query(question)
            assert result is not None
            assert 'query' in result
            assert result['confidence_score'] <= 0.8  # Lower confidence for ambiguous queries
    
    def test_query_with_conflicting_parameters(self, translator):
        """Test query with potentially conflicting parameters."""
        question = "show me minimum maximum generation"  # Conflicting aggregations
        
        result = translator.translate_query(question)
        
        # Should handle gracefully and pick one aggregation
        assert result['parameters']['aggregation'] in ['min', 'max']
    
    def test_query_with_invalid_dates(self, translator):
        """Test query with invalid date formats."""
        question = "data from 2024-13-45 to 2024-99-99"  # Invalid dates
        
        # Should fall back to default time range
        result = translator.translate_query(question)
        
        assert result is not None
        assert result['parameters']['time_range']['relative'] is True
    
    def test_very_long_query(self, translator):
        """Test handling of very long queries."""
        long_question = " ".join([
            "show me the detailed comprehensive analysis of power generation trends",
            "across all regions including southeast northeast south north and central",
            "for all energy sources like hydro wind solar coal gas oil nuclear biomass",
            "with high quality data only and efficiency above 80 percent",
            "grouped by region and energy source and time period",
            "for the last 365 days with hourly aggregation",
            "limited to top 1000 results ordered by generation capacity"
        ])
        
        result = translator.translate_query(long_question)
        
        assert result is not None
        assert len(result['parameters']['regions']) > 0
        assert len(result['parameters']['energy_sources']) > 0
    
    def test_query_with_special_characters(self, translator):
        """Test query with special characters and encoding."""
        question = "generation in São Paulo & Rio de Janeiro (>1000MW) @2024"
        
        # Should handle special characters gracefully
        result = translator.translate_query(question)
        
        assert result is not None
        assert 'query' in result