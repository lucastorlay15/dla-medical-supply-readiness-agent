from pyspark.sql import SparkSession
from pyspark.sql import types as T

from .common import write_delta
from .config import GenerationConfig


REFERENCE_METRICS = [
    (
        "DLA",
        "FY2025 revenue",
        51_800_000_000.0,
        "USD",
        "FY2025",
        "https://www.dla.mil/Info/Annual-Report/",
        "Official DLA enterprise metric. DLA states this scale would place it among the top 100 Fortune 500 companies.",
    ),
    (
        "DLA",
        "FY2025 contract obligations",
        55_800_000_000.0,
        "USD",
        "FY2025",
        "https://www.dla.mil/Info/Annual-Report/",
        "Official DLA enterprise metric across the agency.",
    ),
    (
        "DLA Troop Support Medical",
        "FY2025 dollars obligated",
        10_022_586_655.0,
        "USD",
        "FY2025",
        "https://www.dla.mil/Small-Business/Getting-Started/What-DLA-Buys/",
        "Official DLA Troop Support Medical procurement obligation total.",
    ),
    (
        "DLA Troop Support",
        "global customers supported",
        77_000.0,
        "customers",
        "FY2025/current public description",
        "https://www.dla.mil/About-DLA/News/News-Article-View/Article/4436406/the-digital-quartermaster-creating-digital-powered-supply-chains-for-a-conteste/",
        "Troop Support-wide metric across its supply chains; not Medical-only.",
    ),
    (
        "DLA Troop Support",
        "supplier network",
        2_700.0,
        "suppliers",
        "FY2025/current public description",
        "https://www.dla.mil/About-DLA/News/News-Article-View/Article/4436406/the-digital-quartermaster-creating-digital-powered-supply-chains-for-a-conteste/",
        "Troop Support-wide metric across its supply chains; not Medical-only.",
    ),
    (
        "DLA Troop Support",
        "orders processed annually",
        22_000_000.0,
        "orders (more than)",
        "FY2025",
        "https://www.dla.mil/Portals/104/Documents/Headquarters/History/FY%202025%20History.pdf",
        "Troop Support-wide metric across its four supply chains; public report states more than 22 million orders annually.",
    ),
    (
        "DLA Troop Support",
        "items managed",
        635_400.0,
        "items (more than)",
        "FY2025",
        "https://www.dla.mil/Portals/104/Documents/Headquarters/History/FY%202025%20History.pdf",
        "Troop Support-wide metric across its four supply chains; not Medical-only.",
    ),
]


def build_reference_metrics(spark: SparkSession, cfg: GenerationConfig) -> None:
    schema = T.StructType(
        [
            T.StructField("scope", T.StringType(), False),
            T.StructField("metric_name", T.StringType(), False),
            T.StructField("metric_value", T.DoubleType(), False),
            T.StructField("unit", T.StringType(), False),
            T.StructField("period", T.StringType(), False),
            T.StructField("source_url", T.StringType(), False),
            T.StructField("notes", T.StringType(), False),
        ]
    )
    df = spark.createDataFrame(REFERENCE_METRICS, schema=schema)
    write_delta(
        df,
        spark,
        cfg,
        "reference_enterprise_metrics",
        "Official public DLA scale metrics kept separate from synthetic operational records for demo context and provenance.",
    )
