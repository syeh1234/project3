"""Controlled vocabulary used by the FigureLab classifier and filters.

Keep labels stable: add new values here instead of allowing the model to invent
slightly different labels for the same concept.
"""

PAPER_FIGURE_CATEGORIES = [
    "background", "method", "data", "example", "prompt", "table", "other"
]

SECTION_CATEGORIES = [
    "abstract", "introduction", "background", "related_work", "methods",
    "experimental", "results", "results_and_discussion", "discussion",
    "conclusion", "supplementary", "other", "unknown"
]

PUBLICATION_TYPES = [
    "original_research", "review", "systematic_review", "meta_analysis",
    "methods_paper", "protocol", "case_study", "perspective", "editorial",
    "letter", "data_paper", "conference_paper", "other", "unknown"
]

VISUAL_TYPES = [
    "line_graph", "scatter_plot", "point_or_interval_plot", "bar_graph",
    "grouped_bar_graph", "stacked_bar_graph", "histogram", "box_plot",
    "violin_plot", "heatmap", "contour_plot", "pie_chart", "area_chart",
    "radar_chart", "confusion_matrix", "table", "schematic", "flowchart",
    "workflow_diagram", "mechanism_diagram", "molecular_structure",
    "reaction_scheme", "microscopy_image", "photograph", "map",
    "network_diagram", "3d_surface", "spectrum", "multi_panel", "other"
]

CHART_TYPES = [
    "bar", "line", "scatter", "point", "pie", "heatmap", "contour", "box",
    "violin", "radar", "histogram", "area", "confusion_matrix", "mixed", "other"
]

TECHNIQUE_GROUPS = [
    "spectroscopy", "microscopy", "electrochemistry", "chromatography",
    "thermal_analysis", "diffraction", "mechanical_testing", "synthesis",
    "computational_modeling", "imaging", "other", "unknown"
]

EXPERIMENTAL_TECHNIQUES = [
    "UV-vis spectroscopy", "fluorescence spectroscopy", "FTIR spectroscopy",
    "Raman spectroscopy", "NMR spectroscopy", "X-ray photoelectron spectroscopy",
    "mass spectrometry", "X-ray diffraction", "SEM", "TEM", "AFM",
    "optical microscopy", "confocal microscopy", "cyclic voltammetry",
    "electrochemical impedance spectroscopy", "GC", "HPLC", "TGA", "DSC",
    "tensile testing", "nanoindentation", "contact angle measurement",
    "photolithography", "PECVD", "ALD", "sputtering",
    "molecular dynamics simulation", "density functional theory",
    "finite element analysis", "Monte Carlo simulation", "other", "unknown"
]

VISUALIZATION_PURPOSES = [
    "motivation_or_problem_introduction", "conceptual_explanation",
    "literature_or_prior_work_comparison", "experimental_setup",
    "experimental_workflow", "mechanism_explanation", "data_comparison",
    "trend_over_time_or_condition", "relationship_between_variables",
    "distribution_or_variability", "composition_or_proportion",
    "spatial_distribution", "spectral_characterization",
    "structural_characterization", "model_performance",
    "validation_or_reproducibility", "parameter_sensitivity",
    "summary_or_proposed_model", "other", "unknown"
]

RESEARCH_FIELDS = [
    "chemistry", "materials_science", "chemical_engineering",
    "physics", "biology", "biomedical_science", "environmental_science",
    "computer_science", "engineering", "medicine", "other", "unknown"
]

def section_category(section_title: str) -> str:
    """Map a JATS section heading to a normalized section category."""
    import re
    title = re.sub(r"\s+", " ", (section_title or "").strip().lower())
    if not title:
        return "unknown"

    if any(x in title for x in ("supplement", "supporting information")):
        return "supplementary"
    if "abstract" in title:
        return "abstract"
    if any(x in title for x in ("introduction", "overview", "motivation")):
        return "introduction"
    if any(x in title for x in ("background", "preliminar")):
        return "background"
    if any(x in title for x in ("related work", "literature review", "prior work")):
        return "related_work"
    if any(x in title for x in ("result and discussion", "results and discussion")):
        return "results_and_discussion"
    if any(x in title for x in ("method", "materials", "experimental", "procedure", "fabrication")):
        return "methods" if "method" in title else "experimental"
    if any(x in title for x in ("result", "finding")):
        return "results"
    if "discussion" in title:
        return "discussion"
    if any(x in title for x in ("conclusion", "outlook", "future work")):
        return "conclusion"
    return "other"


def publication_type_from_article_type(article_type: str) -> str:
    value = (article_type or "").lower().replace("-", "_").replace(" ", "_")
    if not value:
        return "unknown"
    if "systematic" in value:
        return "systematic_review"
    if "meta" in value:
        return "meta_analysis"
    if "review" in value:
        return "review"
    if any(x in value for x in ("research", "original", "article")):
        return "original_research"
    if any(x in value for x in ("method", "protocol")):
        return "methods_paper" if "method" in value else "protocol"
    if "case" in value:
        return "case_study"
    if "perspective" in value or "commentary" in value:
        return "perspective"
    if "editorial" in value:
        return "editorial"
    if "letter" in value:
        return "letter"
    if "data" in value:
        return "data_paper"
    return "other"
