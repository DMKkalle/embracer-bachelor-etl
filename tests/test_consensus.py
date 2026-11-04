from embracer_etl.consensus import SourceObservation, weighted_consensus


def test_consensus_accepts_cross_source_agreement():
    observations = [
        SourceObservation("igdb", "release_year", "1993", 1.0),
        SourceObservation("wikidata", "release_year", "1993", 1.0),
        SourceObservation("giantbomb", "release_year", "1994", 0.5),
    ]
    weights = {"igdb": 0.35, "wikidata": 0.35, "giantbomb": 0.30}

    result = weighted_consensus(
        "release_year",
        observations,
        weights,
        accept_threshold=0.60,
        quorum_min_sources=2,
    )

    assert result.value == "1993"
    assert result.review_required is False
    assert result.sources == ("igdb", "wikidata")


def test_consensus_defers_ambiguous_result_to_review():
    observations = [
        SourceObservation("igdb", "release_year", "1995", 0.6),
        SourceObservation("wikidata", "release_year", "1996", 0.6),
    ]
    weights = {"igdb": 0.5, "wikidata": 0.5}

    result = weighted_consensus(
        "release_year",
        observations,
        weights,
        accept_threshold=0.60,
        quorum_min_sources=2,
    )

    assert result.value is None
    assert result.review_required is True
