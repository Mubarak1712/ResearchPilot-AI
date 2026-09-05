"""Transparent lexical rules used by the deterministic evidence extractor."""

METHODOLOGY_SIGNALS = (
    "systematic review",
    "meta-analysis",
    "literature review",
    "machine learning",
    "deep learning",
    "cross-sectional",
    "randomized",
    "questionnaire",
    "observational",
    "case study",
    "cohort",
    "benchmark",
    "simulation",
    "survey",
    "interview",
    "qualitative study",
    "qualitative analysis",
    "qualitative evaluation",
    "quantitative analysis",
    "quantitative evaluation",
    "experimental evaluation",
    "experimental design",
    "experiment",
)

POPULATION_SIGNALS = (
    "participants",
    "patients",
    "students",
    "teachers",
    "employees",
    "organizations",
    "companies",
    "users",
    "consumers",
    "institutions",
    "countries",
    "geographic location",
)

OUTCOME_SIGNALS = (
    "accuracy",
    "performance",
    "satisfaction",
    "adoption",
    "effectiveness",
    "efficiency",
    "mortality",
    "error rate",
    "precision",
    "recall",
    "f1",
    "response time",
    "learning outcomes",
)

COMPARISON_SIGNALS = (
    "compared with",
    "compared to",
    "versus",
    "baseline",
    "control group",
    "outperform",
    "better than",
    "worse than",
)

DATASET_SIGNALS = (
    "benchmark dataset",
    "public dataset",
    "survey data",
    "clinical data",
    "proprietary data",
    "data set",
    "dataset",
    "openalex",
    "kaggle",
    "imagenet",
    "mnist",
)

LIMITATION_SIGNALS = (
    "limitations",
    "limitation",
    "limited by",
    "constrained by",
    "small sample size",
    "small sample",
    "one dataset",
    "lack of",
    "did not include",
    "not considered",
    "future studies should address",
    "cannot generalize",
    "generalizability",
    "restricted to",
)

FUTURE_WORK_SIGNALS = (
    "future work",
    "future research",
    "further research",
    "further studies",
    "future studies",
    "should investigate",
    "should examine",
    "should explore",
    "should be evaluated",
    "remains to be studied",
    "warrants further investigation",
    "additional research is needed",
)

STOPWORDS = frozenset(
    """
    a about after again against all also among an and as at be because before being between
    but by can could do does each every for from further had has have having he her here him
    his how i if in into is it its itself just like me more most my no nor not now of off on
    once one only or other our out over own same she should so some such than that the their
    them themselves then there these they this those through to too under until up very was we
    were what when where which while who why will with would you your yours about after again
    against also among because before being between could every from have into its more most
    other over should such than that their these they this through using were which with would
    study studies paper research result results method methods based data analysis approach work
    for and the of to an in on with is as
    """.split()
)
