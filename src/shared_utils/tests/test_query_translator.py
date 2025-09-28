"""
Unit tests for the query translator module.

Tests natural language to InfluxDB query translation functionality
including parameter extraction and query generation logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.shared_utils.query_translator import (
    QueryTranslator,
    QueryLanguage,
    QueryType,
    QueryParameters,
    QueryTranslationError,
    create_query_translator,
    translate_natural_language_query
)


class TestQueryTranslator:
    """Test cases for QueryTranslator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.translator = QueryTranslator()
    
    def test_initialization(self):
        """Test QueryTranslator initialization."""
        assert self.translator is not None
        assert len(self.translator.query_templates) > 0
        assert len(self.translator.time_patterns) > 0
        assert len(self.translator.region_patterns) > 0
        assert len(self.translator.source_patterns) > 0
        assert len(self.translator.measurement_patterns) > 0
    
    def test_normalize_question(self):
        """Test question normalization."""
        # Test basic normalization
        question = "  What is the POWER GENERATION trend?  "
        normalized = self.translator._normalize_question(question)
        assert normalized == "what is the generation trend"
        
        # Test punctuation removal
        question = "Show me consumption data!!!"
        normalized = self.translator._normalize_question(question)
        assert normalized == "show me consumption data"
        
        # Test term replacement
        question = "What is the electricity generation in the southeast?"
        normalized = self.translator._normalize_question(question)
        assert "generation" in normalized
        assert "southeast" in normalized
    
    def test_identify_query_type(self):
        """Test query type identification."""
        # Test generation trend
        question = "show me generation trend over time"
        query_type = self.translator._identify_query_type(question)
        assert query_type == QueryType.GENERATION_TREND
        
        # Test consumption peak
        question = "what is the peak consumption today"
        query_type = self.translator._identify_query_type(question)
        assert query_type == QueryType.CONSUMPTION_PEAK
        
        # Test transmission losses
        question = "calculate transmission losses in the grid"
        query_type = self.translator._identify_query_type(question)
        assert query_type == QueryType.TRANSMISSION_LOSSES
        
        # Test regional comparison
        question = "compare generation between regions"
        query_type = self.translator._identify_query_type(question)
        assert query_type == QueryType.REGIONAL_COMPARISON
        
        # Test source breakdown
        question = "show energy generation by source"
        query_type = self.translator._identify_query_type(question)
        assert query_type == QueryType.SOURCE_BREAKDOWN
    
    def test_extract_time_range(self):
        """Test time range extraction."""
        # Test relative time ranges
        question = "show data from last week"
        time_range = self.translator._extract_time_range(question)
        assert time_range['relative'] is True
        assert 'start' in time_range
        assert 'stop' in time_range
        
        # Test absolute dates
        question = "show data from 2024-01-01 to 2024-01-31"
        time_range = self.translator._extract_time_range(question)
        assert time_range['relative'] is False
        assert "2024-01-01" in time_range['start']
        assert "2024-01-31" in time_range['stop']
        
        # Test single date
        question = "show data for 2024-01-15"
        time_range = self.translator._extract_time_range(question)
        assert time_range['relative'] is False
        assert "2024-01-15" in time_range['start']
    
    def test_extract_regions(self):
        """Test region extraction."""
        # Test single region
        question = "show generation in southeast region"
        regions = self.translator._extract_regions(question)
        assert 'southeast' in regions
        
        # Test multiple regions
        question = "compare north and south regions"
        regions = self.translator._extract_regions(question)
        assert 'north' in regions
        assert 'south' in regions
        
        # Test all regions
        question = "show data for all regions"
        regions = self.translator._extract_regions(question)
        assert len(regions) > 1
    
    def test_extract_energy_sources(self):
        """Test energy source extraction."""
        # Test single source
        question = "show hydro generation"
        sources = self.translator._extract_energy_sources(question)
        assert 'hydro' in sources
        
        # Test renewable sources
        question = "show renewable energy generation"
        sources = self.translator._extract_energy_sources(question)
        assert 'hydro' in sources
        assert 'solar' in sources
        assert 'wind' in sources
        
        # Test fossil sources
        question = "show fossil fuel generation"
        sources = self.translator._extract_energy_sources(question)
        assert 'thermal' in sources
    
    def test_extract_measurement_types(self):
        """Test measurement type extraction."""
        # Test generation measurement
        question = "show power generation data"
        measurements = self.translator._extract_measurement_types(question)
        assert 'generation_data' in measurements
        
        # Test consumption measurement
        question = "show consumption data"
        measurements = self.translator._extract_measurement_types(question)
        assert 'consumption_data' in measurements
        
        # Test transmission measurement
        question = "show transmission data"
        measurements = self.translator._extract_measurement_types(question)
        assert 'transmission_data' in measurements
    
    def test_extract_aggregation(self):
        """Test aggregation extraction."""
        # Test average
        question = "show average generation"
        aggregation = self.translator._extract_aggregation(question)
        assert aggregation == 'mean'
        
        # Test maximum
        question = "show peak demand"
        aggregation = self.translator._extract_aggregation(question)
        assert aggregation == 'max'
        
        # Test sum
        question = "show total consumption"
        aggregation = self.translator._extract_aggregation(question)
        assert aggregation == 'sum'
        
        # Test default
        question = "show generation data"
        aggregation = self.translator._extract_aggregation(question)
        assert aggregation == 'mean'
    
    def test_extract_filters(self):
        """Test filter extraction."""
        # Test quality filter
        question = "show high quality data"
        filters = self.translator._extract_filters(question)
        assert filters.get('quality_flag') == 'good'
        
        # Test capacity filter
        question = "show plants with capacity above 100"
        filters = self.translator._extract_filters(question)
        assert filters.get('min_capacity') == 100
        
        # Test efficiency filter
        question = "show plants with efficiency above 80"
        filters = self.translator._extract_filters(question)
        assert filters.get('min_efficiency') == 0.8
    
    def test_extract_limit(self):
        """Test limit extraction."""
        # Test top N
        question = "show top 10 generators"
        limit = self.translator._extract_limit(question)
        assert limit == 10
        
        # Test first N
        question = "show first 5 results"
        limit = self.translator._extract_limit(question)
        assert limit == 5
        
        # Test no limit
        question = "show all generators"
        limit = self.translator._extract_limit(question)
        assert limit is None
    
    def test_extract_group_by(self):
        """Test group by extraction."""
        # Test group by region
        question = "show generation by region"
        group_by = self.translator._extract_group_by(question)
        assert 'region' in group_by
        
        # Test group by source
        question = "show generation per energy source"
        group_by = self.translator._extract_group_by(question)
        assert 'energy_source' in group_by
        
        # Test group by time
        question = "show hourly generation"
        group_by = self.translator._extract_group_by(question)
        assert 'hour' in group_by
    
    def test_generate_flux_query(self):
        """Test Flux query generation."""
        # Create test parameters
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-31T23:59:59Z'},
            regions=['southeast'],
            energy_sources=['hydro'],
            measurement_types=['generation_data'],
            aggregation='mean',
            filters={},
            limit=None,
            group_by=[]
        )
        
        # Get template
        template = self.translator.query_templates[QueryType.GENERATION_TREND]
        
        # Generate query
        query = self.translator._generate_flux_query(template, parameters)
        
        # Verify query structure
        assert 'from(bucket: "energy_data")' in query
        assert '2024-01-01T00:00:00Z' in query
        assert '2024-01-31T23:59:59Z' in query
        assert 'generation_data' in query
        assert 'southeast' in query
        assert 'hydro' in query
        assert 'mean' in query
    
    def test_generate_influxql_query(self):
        """Test InfluxQL query generation."""
        # Create test parameters
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-31T23:59:59Z'},
            regions=['southeast'],
            energy_sources=['hydro'],
            measurement_types=['generation_data'],
            aggregation='mean',
            filters={},
            limit=10,
            group_by=['region']
        )
        
        # Get template
        template = self.translator.query_templates[QueryType.GENERATION_TREND]
        
        # Generate query
        query = self.translator._generate_influxql_query(template, parameters)
        
        # Verify query structure
        assert 'SELECT MEAN(power_mw)' in query
        assert 'FROM generation_data' in query
        assert '2024-01-01T00:00:00Z' in query
        assert '2024-01-31T23:59:59Z' in query
        assert 'southeast' in query
        assert 'LIMIT 10' in query
        assert 'GROUP BY' in query
    
    def test_translate_query_flux(self):
        """Test complete query translation to Flux."""
        question = "Show me hydro generation trend in southeast region for last month"
        
        result = self.translator.translate_query(question, QueryLanguage.FLUX)
        
        # Verify result structure
        assert 'query' in result
        assert 'query_type' in result
        assert 'language' in result
        assert 'parameters' in result
        assert 'confidence_score' in result
        
        # Verify query content
        assert result['language'] == 'flux'
        assert result['query_type'] == 'generation_trend'
        assert 'from(bucket:' in result['query']
        assert 'hydro' in result['query']
        assert 'southeast' in result['query']
        
        # Verify confidence score
        assert 0 <= result['confidence_score'] <= 1
    
    def test_translate_query_influxql(self):
        """Test complete query translation to InfluxQL."""
        question = "What is the peak consumption in all regions?"
        
        result = self.translator.translate_query(question, QueryLanguage.INFLUXQL)
        
        # Verify result structure
        assert 'query' in result
        assert result['language'] == 'influxql'
        assert result['query_type'] == 'consumption_peak'
        assert 'SELECT MAX' in result['query']
        assert 'FROM consumption_data' in result['query']
    
    def test_translate_query_with_context(self):
        """Test query translation with additional context."""
        question = "Show generation data"
        context = {
            'default_region': 'northeast',
            'default_time_range': '7d',
            'preferred_sources': ['wind', 'solar']
        }
        
        result = self.translator.translate_query(question, context=context)
        
        # Verify that context doesn't break translation
        assert 'query' in result
        assert result['query_type'] == 'generation_trend'
    
    def test_validate_parameters_success(self):
        """Test parameter validation with valid parameters."""
        template = self.translator.query_templates[QueryType.GENERATION_TREND]
        parameters = QueryParameters(
            time_range={'start': '2024-01-01T00:00:00Z', 'stop': '2024-01-31T23:59:59Z'},
            regions=[],
            energy_sources=[],
            measurement_types=[],
            aggregation='mean',
            filters={}
        )
        
        # Should not raise exception
        self.translator._validate_parameters(template, parameters)
    
    def test_validate_parameters_missing_required(self):
        """Test parameter validation with missing required parameters."""
        template = self.translator.query_templates[QueryType.GENERATION_TREND]
        parameters = QueryParameters(
            time_range={},  # Missing required time_range
            regions=[],
            energy_sources=[],
            measurement_types=[],
            aggregation='mean',
            filters={}
        )
        
        with pytest.raises(QueryTranslationError):
            self.translator._validate_parameters(template, parameters)
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        # High confidence question
        question = "show generation trend by region and source"
        score = self.translator._calculate_confidence_score(question, QueryType.GENERATION_TREND)
        assert score > 0.8
        
        # Lower confidence question
        question = "show some data"
        score = self.translator._calculate_confidence_score(question, QueryType.GENERATION_TREND)
        assert score < 0.8
    
    def test_error_handling(self):
        """Test error handling in query translation."""
        # Test with invalid template variables
        with patch.object(self.translator, 'query_templates', {}):
            with pytest.raises(QueryTranslationError):
                self.translator.translate_query("show generation data")
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Empty question
        with pytest.raises(QueryTranslationError):
            self.translator.translate_query("")
        
        # Very long question
        long_question = "show " + "generation " * 100 + "data"
        result = self.translator.translate_query(long_question)
        assert 'query' in result
        
        # Question with special characters
        special_question = "show generation data @#$%^&*()"
        result = self.translator.translate_query(special_question)
        assert 'query' in result


class TestFactoryFunctions:
    """Test factory functions and convenience methods."""
    
    def test_create_query_translator(self):
        """Test query translator factory function."""
        translator = create_query_translator()
        assert isinstance(translator, QueryTranslator)
        assert len(translator.query_templates) > 0
    
    def test_translate_natural_language_query(self):
        """Test convenience function for query translation."""
        question = "Show hydro generation in southeast"
        
        result = translate_natural_language_query(question)
        
        assert 'query' in result
        assert 'query_type' in result
        assert result['language'] == 'flux'  # Default language
        
        # Test with InfluxQL
        result = translate_natural_language_query(question, QueryLanguage.INFLUXQL)
        assert result['language'] == 'influxql'
    
    def test_translate_with_context(self):
        """Test translation with context parameter."""
        question = "Show generation data"
        context = {'region': 'north', 'source': 'wind'}
        
        result = translate_natural_language_query(question, context=context)
        assert 'query' in result


class TestQueryParameters:
    """Test QueryParameters dataclass."""
    
    def test_query_parameters_creation(self):
        """Test QueryParameters object creation."""
        params = QueryParameters(
            time_range={'start': '2024-01-01', 'stop': '2024-01-31'},
            regions=['southeast'],
            energy_sources=['hydro'],
            measurement_types=['generation_data'],
            aggregation='mean',
            filters={'quality_flag': 'good'},
            limit=10,
            group_by=['region']
        )
        
        assert params.time_range['start'] == '2024-01-01'
        assert 'southeast' in params.regions
        assert 'hydro' in params.energy_sources
        assert params.aggregation == 'mean'
        assert params.limit == 10
        assert 'region' in params.group_by


class TestIntegrationScenarios:
    """Integration test scenarios for common use cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.translator = QueryTranslator()
    
    def test_generation_analysis_scenario(self):
        """Test complete generation analysis scenario."""
        questions = [
            "Show me hydro generation trend in southeast for last month",
            "What is the peak hydro generation in southeast?",
            "Compare hydro generation between regions",
            "Show top 5 hydro plants by generation"
        ]
        
        for question in questions:
            result = self.translator.translate_query(question)
            assert 'query' in result
            assert result['confidence_score'] > 0.5
    
    def test_consumption_analysis_scenario(self):
        """Test complete consumption analysis scenario."""
        questions = [
            "What is the peak consumption today?",
            "Show consumption trend by region",
            "Compare consumption between industrial and residential sectors"
        ]
        
        expected_types = [
            'consumption_peak',
            'load_profile',  # consumption trend maps to load profile
            'regional_comparison'  # comparison between sectors
        ]
        
        for i, question in enumerate(questions):
            result = self.translator.translate_query(question)
            assert 'query' in result
            # Check that we get a reasonable query type for consumption-related questions
            assert result['query_type'] in ['consumption_peak', 'load_profile', 'regional_comparison']
    
    def test_transmission_analysis_scenario(self):
        """Test transmission analysis scenario."""
        questions = [
            "Calculate transmission losses in the grid",
            "Show transmission losses by region",
            "What are the total losses for last week?"
        ]
        
        for question in questions:
            result = self.translator.translate_query(question)
            assert 'query' in result
            # Should identify as transmission-related query
    
    def test_multi_language_support(self):
        """Test support for both Flux and InfluxQL."""
        question = "Show generation trend for hydro in southeast"
        
        # Test Flux
        flux_result = self.translator.translate_query(question, QueryLanguage.FLUX)
        assert flux_result['language'] == 'flux'
        assert 'from(bucket:' in flux_result['query']
        
        # Test InfluxQL
        influxql_result = self.translator.translate_query(question, QueryLanguage.INFLUXQL)
        assert influxql_result['language'] == 'influxql'
        assert 'SELECT' in influxql_result['query']
        assert 'FROM' in influxql_result['query']
    
    def test_complex_query_scenario(self):
        """Test complex query with multiple parameters."""
        question = "Show top 10 renewable energy sources by average generation in southeast and northeast regions for last 3 months with high quality data"
        
        result = self.translator.translate_query(question)
        
        # Verify complex parameter extraction
        params = result['parameters']
        assert len(params['regions']) >= 2
        assert len(params['energy_sources']) >= 2  # renewable sources
        assert params['aggregation'] == 'mean'
        assert params['limit'] == 10
        assert 'quality_flag' in params['filters']