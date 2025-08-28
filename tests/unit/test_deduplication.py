#!/usr/bin/env python3
"""
Unit tests for deduplication logic.
Tests ECLI-based deduplication and file removal.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.transformer import TwoPhaseTransformerWithDedup


class TestDeduplication:
    """Test deduplication functionality."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def transformer(self, temp_output_dir):
        """Create a transformer with temp directories."""
        temp_input = temp_output_dir / 'input'
        temp_input.mkdir()
        return TwoPhaseTransformerWithDedup(str(temp_input), str(temp_output_dir))
    
    def create_test_file(self, output_dir, filename, ecli, ecli_aliases=None):
        """Helper to create a test JSON file."""
        doc = {
            'file_name': filename,
            'decision_id': ecli,
            'ecli_alias': ecli_aliases or [],
            'language_metadata': 'FR',
            'isValid': True
        }
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(doc, f)
        return filepath
    
    def test_ecli_to_filename_conversion(self, transformer):
        """Test ECLI to filename conversion."""
        ecli = 'ECLI:BE:CASS:2023:ARR.20230117.2N.7'
        
        # Test with specific language
        filenames = transformer.ecli_to_filename(ecli, 'FR')
        assert len(filenames) == 1
        assert filenames[0] == 'juportal.be_ECLI_BE_CASS_2023_ARR.20230117.2N.7_FR.json'
        
        # Test without language (all languages)
        filenames = transformer.ecli_to_filename(ecli)
        assert len(filenames) == 3
        assert 'juportal.be_ECLI_BE_CASS_2023_ARR.20230117.2N.7_FR.json' in filenames
        assert 'juportal.be_ECLI_BE_CASS_2023_ARR.20230117.2N.7_NL.json' in filenames
        assert 'juportal.be_ECLI_BE_CASS_2023_ARR.20230117.2N.7_DE.json' in filenames
    
    def test_ecli_to_filename_invalid(self, transformer):
        """Test ECLI to filename conversion with invalid input."""
        assert transformer.ecli_to_filename('', 'FR') == []
        assert transformer.ecli_to_filename(None, 'FR') == []
        assert transformer.ecli_to_filename('NOT_AN_ECLI', 'FR') == []
    
    def test_deduplication_simple(self, transformer, temp_output_dir):
        """Test simple deduplication case."""
        # Create main file
        main_file = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            []
        )
        
        # Create duplicate file (referenced as alias in main file)
        dup_file = self.create_test_file(
            temp_output_dir,
            'file2.json',
            'ECLI:BE:CASS:2023:ARR.456',
            []
        )
        
        # Update main file to include alias
        self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            ['ECLI:BE:CASS:2023:ARR.456']
        )
        
        # Run deduplication
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # Main file should exist, duplicate should be removed
        assert main_file.exists()
        assert not dup_file.exists()
        assert transformer.stats['duplicates_removed'] == 1
    
    def test_deduplication_multiple_aliases(self, transformer, temp_output_dir):
        """Test deduplication with multiple aliases."""
        # Create main file with multiple aliases
        main_file = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            ['ECLI:BE:CASS:2023:ARR.456', 'ECLI:BE:CASS:2023:ARR.789']
        )
        
        # Create duplicate files
        dup1 = self.create_test_file(
            temp_output_dir,
            'file2.json',
            'ECLI:BE:CASS:2023:ARR.456',
            []
        )
        
        dup2 = self.create_test_file(
            temp_output_dir,
            'file3.json',
            'ECLI:BE:CASS:2023:ARR.789',
            []
        )
        
        # Run deduplication
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # Main file should exist, duplicates should be removed
        assert main_file.exists()
        assert not dup1.exists()
        assert not dup2.exists()
        assert transformer.stats['duplicates_removed'] == 2
    
    def test_deduplication_no_duplicates(self, transformer, temp_output_dir):
        """Test deduplication when there are no duplicates."""
        # Create files with no overlapping ECLIs
        file1 = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            []
        )
        
        file2 = self.create_test_file(
            temp_output_dir,
            'file2.json',
            'ECLI:BE:CASS:2023:ARR.456',
            []
        )
        
        # Run deduplication
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # Both files should still exist
        assert file1.exists()
        assert file2.exists()
        assert transformer.stats['duplicates_removed'] == 0
    
    def test_deduplication_skip_invalid_files(self, transformer, temp_output_dir):
        """Test that invalid_files.json is skipped."""
        # Create invalid_files.json
        invalid_file = temp_output_dir / 'invalid_files.json'
        with open(invalid_file, 'w') as f:
            json.dump(['some_file.json'], f)
        
        # Create regular file
        regular_file = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            []
        )
        
        # Run deduplication
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # Both files should still exist
        assert invalid_file.exists()
        assert regular_file.exists()
    
    def test_deduplication_circular_references(self, transformer, temp_output_dir):
        """Test deduplication with circular alias references."""
        # Create two files that reference each other
        file1 = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            ['ECLI:BE:CASS:2023:ARR.456']
        )
        
        file2 = self.create_test_file(
            temp_output_dir,
            'file2.json',
            'ECLI:BE:CASS:2023:ARR.456',
            ['ECLI:BE:CASS:2023:ARR.123']
        )
        
        # Run deduplication
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # One should be removed (first processed wins)
        existing_files = list(temp_output_dir.glob('*.json'))
        assert len(existing_files) == 1
    
    def test_deduplication_invalid_alias_format(self, transformer, temp_output_dir):
        """Test deduplication with invalid alias formats."""
        # Create file with invalid aliases
        file1 = self.create_test_file(
            temp_output_dir,
            'file1.json',
            'ECLI:BE:CASS:2023:ARR.123',
            ['NOT_AN_ECLI', '', None, 'ECLI:BE:CASS:2023:ARR.456']
        )
        
        file2 = self.create_test_file(
            temp_output_dir,
            'file2.json',
            'ECLI:BE:CASS:2023:ARR.456',
            []
        )
        
        # Run deduplication (should handle invalid aliases gracefully)
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # File2 should be removed due to valid alias
        assert file1.exists()
        assert not file2.exists()
    
    def test_deduplication_error_handling(self, transformer, temp_output_dir):
        """Test deduplication error handling."""
        # Create a file with invalid JSON
        bad_file = temp_output_dir / 'bad.json'
        with open(bad_file, 'w') as f:
            f.write('{ invalid json')
        
        # Create valid file
        good_file = self.create_test_file(
            temp_output_dir,
            'good.json',
            'ECLI:BE:CASS:2023:ARR.123',
            []
        )
        
        # Run deduplication (should continue despite error)
        transformer.output_dir = temp_output_dir
        transformer.deduplicate_files()
        
        # Good file should still exist
        assert good_file.exists()


class TestGermanFileRemoval:
    """Test German file removal functionality."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def transformer(self, temp_output_dir):
        """Create a transformer with temp directories."""
        temp_input = temp_output_dir / 'input'
        temp_input.mkdir()
        return TwoPhaseTransformerWithDedup(str(temp_input), str(temp_output_dir))
    
    def test_remove_german_files(self, transformer, temp_output_dir):
        """Test removal of German language files."""
        # Create German file
        de_file = temp_output_dir / 'test_DE.json'
        with open(de_file, 'w') as f:
            json.dump({'language_metadata': 'DE', 'file_name': 'test_DE.json'}, f)
        
        # Create French file
        fr_file = temp_output_dir / 'test_FR.json'
        with open(fr_file, 'w') as f:
            json.dump({'language_metadata': 'FR', 'file_name': 'test_FR.json'}, f)
        
        # Create Dutch file
        nl_file = temp_output_dir / 'test_NL.json'
        with open(nl_file, 'w') as f:
            json.dump({'language_metadata': 'NL', 'file_name': 'test_NL.json'}, f)
        
        # Run German file removal
        transformer.output_dir = temp_output_dir
        transformer.remove_german_files()
        
        # German file should be removed, others should remain
        assert not de_file.exists()
        assert fr_file.exists()
        assert nl_file.exists()
        assert transformer.stats['german_files_removed'] == 1
    
    def test_remove_german_files_skip_invalid(self, transformer, temp_output_dir):
        """Test that invalid_files.json is skipped during German removal."""
        # Create invalid_files.json
        invalid_file = temp_output_dir / 'invalid_files.json'
        with open(invalid_file, 'w') as f:
            json.dump(['some_file.json'], f)
        
        # Run German file removal
        transformer.output_dir = temp_output_dir
        transformer.remove_german_files()
        
        # Invalid file should still exist
        assert invalid_file.exists()


class TestMissingDatesAnalysis:
    """Test missing dates analysis functionality."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def transformer(self, temp_output_dir):
        """Create a transformer with temp directories."""
        temp_input = temp_output_dir / 'input'
        temp_input.mkdir()
        return TwoPhaseTransformerWithDedup(str(temp_input), str(temp_output_dir))
    
    def test_count_missing_dates(self, transformer, temp_output_dir):
        """Test counting of missing dates."""
        # Create file with complete date
        complete_file = temp_output_dir / 'complete.json'
        with open(complete_file, 'w') as f:
            json.dump({
                'file_name': 'complete.json',
                'decision_date': '2023-01-15',
                'isValid': True
            }, f)
        
        # Create file with year-only date
        year_only_file = temp_output_dir / 'year_only.json'
        with open(year_only_file, 'w') as f:
            json.dump({
                'file_name': 'year_only.json',
                'decision_date': '2023',
                'isValid': True
            }, f)
        
        # Create file with missing date
        missing_file = temp_output_dir / 'missing.json'
        with open(missing_file, 'w') as f:
            json.dump({
                'file_name': 'missing.json',
                'decision_date': '',
                'isValid': True
            }, f)
        
        # Create invalid file (should be skipped)
        invalid_file = temp_output_dir / 'invalid.json'
        with open(invalid_file, 'w') as f:
            json.dump({
                'file_name': 'invalid.json',
                'decision_date': '2023-01-15',
                'isValid': False
            }, f)
        
        # Run missing dates analysis
        transformer.output_dir = temp_output_dir
        transformer.count_missing_dates()
        
        # Check statistics
        assert transformer.stats['valid_with_dates_count'] == 1
        assert transformer.stats['missing_dates_count'] == 2  # year_only and missing
        
        # Check that missing dates file was created
        missing_dates_file = temp_output_dir / 'missing_dates.json'
        assert missing_dates_file.exists()
        
        with open(missing_dates_file, 'r') as f:
            missing_data = json.load(f)
            assert missing_data['count'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])