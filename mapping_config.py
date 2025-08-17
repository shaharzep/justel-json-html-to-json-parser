"""
Language-specific field mappings for Juportal JSON transformation.
Parsed from Sheet1.csv and used to map legend text to schema fields.
"""

import csv
import re
from typing import Dict, List, Optional, Tuple

class FieldMapper:
    """Handles language-specific field mappings for Juportal documents."""
    
    def __init__(self, csv_path: str = "Sheet1.csv"):
        """Initialize mapper with CSV file containing field mappings."""
        self.mappings = self._load_mappings(csv_path)
        self.legend_patterns = self._compile_legend_patterns()
        
    def _load_mappings(self, csv_path: str) -> Dict[str, Dict[str, List[str]]]:
        """Load mappings from CSV file."""
        mappings = {}
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or not row[0] or row[0] == '---':
                        continue
                    
                    field_name = row[0].strip()
                    # Store all non-empty legend texts for this field
                    legends = []
                    for cell in row[1:]:
                        cell = cell.strip()
                        if cell and cell not in ['', '""']:
                            # Remove surrounding quotes and clean up
                            cell = cell.strip('"').strip()
                            if cell:
                                legends.append(cell)
                    
                    if legends:
                        mappings[field_name] = {
                            'legends': legends,
                            'patterns': self._create_patterns(legends)
                        }
        except FileNotFoundError:
            # Fallback mappings if CSV not found
            mappings = self._get_default_mappings()
            
        return mappings
    
    def _create_patterns(self, legends: List[str]) -> List[re.Pattern]:
        """Create regex patterns from legend texts."""
        patterns = []
        for legend in legends:
            # Escape special regex characters but keep wildcards
            pattern = re.escape(legend)
            # Make colon optional at the end
            pattern = pattern.replace(r'\:', r':?')
            # Make the pattern case-insensitive and allow whitespace variations
            patterns.append(re.compile(pattern, re.IGNORECASE))
        return patterns
    
    def _compile_legend_patterns(self) -> Dict[str, re.Pattern]:
        """Compile special legend patterns for section identification."""
        return {
            'decision_card_fr': re.compile(r"Jugement/arrêt\s+du\s+(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE),
            'decision_card_nl': re.compile(r"Vonnis/arrest\s+van\s+(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE),
            'decision_card_de': re.compile(r"Urteil\s+vom\s+(\d{1,2})\s+(\w+)\s+(\d{4})", re.IGNORECASE),
            'fiche_single': re.compile(r"Fiche\s+(\d+)", re.IGNORECASE),
            'fiche_range': re.compile(r"Fiches?\s+(\d+)\s*[-–]\s*(\d+)", re.IGNORECASE),
            'fiche_simple': re.compile(r"Fiche\s*$", re.IGNORECASE),
        }
    
    def identify_field(self, text: str) -> Optional[str]:
        """Identify field name from legend text."""
        if not text:
            return None
            
        text = text.strip()
        
        # Check each field's patterns
        for field_name, field_info in self.mappings.items():
            for pattern in field_info.get('patterns', []):
                if pattern.match(text):
                    return field_name
                    
        return None
    
    def is_decision_card(self, legend: str) -> bool:
        """Check if legend indicates a decision card (first card)."""
        if not legend:
            return False
            
        patterns = [
            self.legend_patterns['decision_card_fr'],
            self.legend_patterns['decision_card_nl'],
            self.legend_patterns['decision_card_de']
        ]
        
        return any(pattern.match(legend) for pattern in patterns)
    
    def is_fiche_card(self, legend: str) -> bool:
        """Check if legend indicates a Fiche card."""
        if not legend:
            return False
            
        patterns = [
            self.legend_patterns['fiche_single'],
            self.legend_patterns['fiche_range'],
            self.legend_patterns['fiche_simple']
        ]
        
        return any(pattern.match(legend) for pattern in patterns)
    
    def extract_fiche_numbers(self, legend: str) -> List[str]:
        """Extract Fiche numbers from legend."""
        numbers = []
        
        # Check for range pattern (e.g., "Fiches 2 - 9")
        range_match = self.legend_patterns['fiche_range'].match(legend)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            numbers = [str(i) for i in range(start, end + 1)]
        else:
            # Check for single number
            single_match = self.legend_patterns['fiche_single'].match(legend)
            if single_match:
                numbers = [single_match.group(1)]
            elif self.legend_patterns['fiche_simple'].match(legend):
                # Simple "Fiche" without number, assume 1
                numbers = ['1']
                
        return numbers
    
    def is_full_text_section(self, legend: str) -> bool:
        """Check if legend indicates full text section."""
        if not legend:
            return False
            
        full_text_patterns = [
            "Texte de la décision",
            "Texte des conclusions", 
            "Tekst van de beslissing",
            "Tekst van de conclusie",
            "Text der Entscheidung"
        ]
        
        legend_lower = legend.lower()
        return any(pattern.lower() in legend_lower for pattern in full_text_patterns)
    
    def is_related_publications(self, legend: str) -> bool:
        """Check if legend indicates related publications section."""
        if not legend:
            return False
            
        patterns = [
            "Publication(s) liée(s)",
            "Gerelateerde publicatie(s)",
            "Verwandte Veröffentlichung(en)"
        ]
        
        legend_lower = legend.lower()
        return any(pattern.lower() in legend_lower for pattern in patterns)
    
    def _get_default_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        """Get default mappings if CSV is not available."""
        return {
            'ecli': {
                'legends': ['No ECLI:', 'ECLI nr:', 'ECLI-Nummer:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['No ECLI:?', 'ECLI nr:?', 'ECLI-Nummer:?']]
            },
            'rolNumber': {
                'legends': ['No Rôle:', 'Rolnummer:', 'Aktenzeichen:', 'No Arrêt/No Rôle:', 'Arrest- Rolnummer:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['No Rôle:?', 'Rolnummer:?', 'Aktenzeichen:?']]
            },
            'chamber': {
                'legends': ['Chambre:', 'Kamer:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Chambre:?', 'Kamer:?']]
            },
            'fieldOfLaw': {
                'legends': ['Domaine juridique:', 'Rechtsgebied:', 'Rechtsgebiet:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Domaine juridique:?', 'Rechtsgebied:?']]
            },
            'case': {
                'legends': ['Affaire:', 'Zaak:', 'Sache:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Affaire:?', 'Zaak:?', 'Sache:?']]
            },
            'versions': {
                'legends': ['Version(s):', 'Versie(s):', 'Version(en):'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Version\\(s\\):?', 'Versie\\(s\\):?']]
            },
            'keywordsCassation': {
                'legends': ['Thésaurus Cassation:', 'Thesaurus CAS:', 'Thesaurus CASS:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Thésaurus Cassation:?', 'Thesaurus CAS:?']]
            },
            'keywordsUtu': {
                'legends': ['Thésaurus UTU:', 'UTU-thesaurus:', 'UTU Thesaurus:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Thésaurus UTU:?', 'UTU-thesaurus:?']]
            },
            'keywordsFree': {
                'legends': ['Mots libres:', 'Vrije woorden:', 'Freie Wörter:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Mots libres:?', 'Vrije woorden:?']]
            },
            'legalBasis': {
                'legends': ['Bases légales:', 'Wettelijke bepalingen:', 'Rechtsgrundlage:'],
                'patterns': [re.compile(p, re.IGNORECASE) for p in ['Bases légales:?', 'Wettelijke bepalingen:?']]
            }
        }