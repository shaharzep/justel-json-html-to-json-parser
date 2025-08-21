"""Sample input data for testing"""

# Sample raw input JSON structure
SAMPLE_RAW_JSON = {
    "file": "test_file.txt",
    "lang": "FR",
    "title": "ECLI:BE:CASS:2007:ARR.20070622.5",
    "sections": [
        {
            "legend": "Jugement/arrêt du 22 juin 2007",
            "paragraphs": [
                {
                    "text": "No ECLI:",
                    "html": "<p>No ECLI:</p>"
                },
                {
                    "text": "ECLI:BE:CASS:2007:ARR.20070622.5",
                    "html": "<p>ECLI:BE:CASS:2007:ARR.20070622.5</p>"
                },
                {
                    "text": "No Rôle:",
                    "html": "<p>No Rôle:</p>"
                },
                {
                    "text": "C.05.0032.N",
                    "html": "<p>C.05.0032.N</p>"
                },
                {
                    "text": "Chambre:",
                    "html": "<p>Chambre:</p>"
                },
                {
                    "text": "1N - eerste kamer",
                    "html": "<p>1N - eerste kamer</p>"
                },
                {
                    "text": "Domaine juridique:",
                    "html": "<p>Domaine juridique:</p>"
                },
                {
                    "text": "Autres - Droit civil",
                    "html": "<p>Autres - Droit civil</p>"
                }
            ]
        },
        {
            "legend": "Fiche 1",
            "paragraphs": [
                {
                    "text": "This is a summary text for the notice.",
                    "html": "<p>This is a summary text for the notice.</p>"
                },
                {
                    "text": "Thésaurus Cassation:",
                    "html": "<p>Thésaurus Cassation:</p>"
                },
                {
                    "text": "SIGNIFICATIONS ET NOTIFICATIONS - GENERALITES",
                    "html": "<p>SIGNIFICATIONS ET NOTIFICATIONS - GENERALITES<br/>DOMICILE</p>"
                },
                {
                    "text": "Thésaurus UTU:",
                    "html": "<p>Thésaurus UTU:</p>"
                },
                {
                    "text": "DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX",
                    "html": "<p>DROIT JUDICIAIRE - PRINCIPES GÉNÉRAUX</p>"
                },
                {
                    "text": "Mots libres:",
                    "html": "<p>Mots libres:</p>"
                },
                {
                    "text": "Domicile élu chez un mandataire",
                    "html": "<p>Domicile élu chez un mandataire</p>"
                },
                {
                    "text": "Bases légales:",
                    "html": "<p>Bases légales:</p>"
                },
                {
                    "text": "Code Judiciaire - 10-10-1967 - Art. 35, 36 et 39",
                    "html": "<p>Code Judiciaire - 10-10-1967 - Art. 35, 36 et 39<br/>Code Civil - Art. 111</p>"
                }
            ]
        },
        {
            "legend": "Texte de la décision",
            "paragraphs": [
                {
                    "text": "N° C.05.0032.N",
                    "html": "<p>N° C.05.0032.N</p>"
                },
                {
                    "text": "AVERO BELGIUM INSURANCE",
                    "html": "<p>AVERO BELGIUM INSURANCE</p>"
                },
                {
                    "text": "contre",
                    "html": "<p>contre</p>"
                },
                {
                    "text": "WALK ABOUT, société anonyme",
                    "html": "<p>WALK ABOUT, société anonyme</p>"
                },
                {
                    "text": "La procédure devant la Cour",
                    "html": "<p>La procédure devant la Cour</p>"
                },
                {
                    "text": "Document PDF ECLI:BE:CASS:2007:ARR.20070622.5",
                    "html": "<p>Document PDF ECLI:BE:CASS:2007:ARR.20070622.5</p>",
                    "links": [
                        {
                            "href": "/JUPORTAwork/ECLI:BE:CASS:2007:ARR.20070622.5_FR.pdf",
                            "text": "Document PDF"
                        }
                    ]
                }
            ]
        },
        {
            "legend": "Publications connexes", 
            "paragraphs": [
                {
                    "text": "Cité par:",
                    "html": "<p>Cité par:</p>"
                },
                {
                    "text": "ECLI:BE:CASS:2010:CONC.20100226.8",
                    "html": "<p>ECLI:BE:CASS:2010:CONC.20100226.8</p>"
                },
                {
                    "text": "ECLI:BE:CASS:2015:CONC.20150925.3",
                    "html": "<p>ECLI:BE:CASS:2015:CONC.20150925.3</p>"
                },
                {
                    "text": "Voir plus récemment:",
                    "html": "<p>Voir plus récemment:</p>"
                },
                {
                    "text": "ECLI:BE:CASS:2012:ARR.20120112.2",
                    "html": "<p>ECLI:BE:CASS:2012:ARR.20120112.2</p>"
                }
            ]
        }
    ]
}

# Sample with multi-fiche
SAMPLE_MULTI_FICHE = {
    "sections": [
        {
            "legend": "Fiches 1 - 3",
            "paragraphs": [
                {
                    "text": "Summary for multiple fiches",
                    "html": "<p>Summary for multiple fiches</p>"
                },
                {
                    "text": "Thésaurus Cassation:",
                    "html": "<p>Thésaurus Cassation:</p>"
                },
                {
                    "text": "KEYWORD1",
                    "html": "<p>KEYWORD1<br/>KEYWORD2<br/>KEYWORD3</p>"
                },
                {
                    "text": "Thésaurus Cassation:",
                    "html": "<p>Thésaurus Cassation:</p>"
                },
                {
                    "text": "KEYWORD4",
                    "html": "<p>KEYWORD4</p>"
                }
            ]
        }
    ]
}

# Sample Dutch document
SAMPLE_DUTCH_JSON = {
    "file": "test_nl.txt",
    "lang": "NL",
    "title": "ECLI:BE:CASS:2007:ARR.20070622.5",
    "sections": [
        {
            "legend": "Vonnis/arrest van 22 juni 2007",
            "paragraphs": [
                {
                    "text": "Nr. ECLI:",
                    "html": "<p>Nr. ECLI:</p>"
                },
                {
                    "text": "ECLI:BE:CASS:2007:ARR.20070622.5",
                    "html": "<p>ECLI:BE:CASS:2007:ARR.20070622.5</p>"
                }
            ]
        },
        {
            "legend": "Fiche 1",
            "paragraphs": [
                {
                    "text": "Dit is een samenvatting.",
                    "html": "<p>Dit is een samenvatting.</p>"
                },
                {
                    "text": "Thesaurus Cassatie:",
                    "html": "<p>Thesaurus Cassatie:</p>"
                },
                {
                    "text": "BETEKENINGEN EN KENNISGEVINGEN",
                    "html": "<p>BETEKENINGEN EN KENNISGEVINGEN</p>"
                },
                {
                    "text": "Vrije woorden:",
                    "html": "<p>Vrije woorden:</p>"
                },
                {
                    "text": "Gekozen woonplaats",
                    "html": "<p>Gekozen woonplaats</p>"
                },
                {
                    "text": "Wettelijke bepalingen:",
                    "html": "<p>Wettelijke bepalingen:</p>"
                },
                {
                    "text": "Gerechtelijk Wetboek - Art. 39",
                    "html": "<p>Gerechtelijk Wetboek - Art. 39</p>"
                }
            ]
        }
    ]
}

# Sample German document
SAMPLE_GERMAN_JSON = {
    "file": "test_de.txt",
    "lang": "DE",
    "title": "ECLI:BE:GHCC:2022:ARR.103",
    "sections": [
        {
            "legend": "Urteil vom 14 Juli 2022",
            "paragraphs": []
        }
    ]
}

# Edge cases
EMPTY_SECTIONS = {
    "file": "empty.txt",
    "lang": "FR",
    "title": "ECLI:BE:TEST:2024:ARR.001",
    "sections": []
}

MISSING_FIELDS = {
    "file": "missing.txt",
    "lang": "FR",
    "sections": [
        {
            "legend": "Jugement/arrêt du 1 janvier 2024",
            "paragraphs": []
        }
    ]
}

# Sample with complex legal basis
COMPLEX_LEGAL_BASIS = {
    "sections": [
        {
            "legend": "Fiche 1",
            "paragraphs": [
                {
                    "text": "Bases légales:",
                    "html": "<p>Bases légales:</p>"
                },
                {
                    "text": "",
                    "html": "<p>Loi - 09-08-1963 - 62 - 01 ELI link Pub nr 1963080914<br/>Koninklijk Besluit - 04-11-1963 - 169 - 01 ELI link Pub nr 1963110402<br/>Directive 2010/13/UE - Article 3</p>"
                }
            ]
        }
    ]
}