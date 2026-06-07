from app.db.base import Base
from app.evaluation.retrieval import (
    ExpectedRetrievalResult,
    RetrievalEvalCase,
    RetrievalEvalChunk,
    RetrievalEvalDataset,
    RetrievalEvalDocument,
    load_retrieval_eval_dataset,
    matches_expected_result,
    run_retrieval_comparison,
    run_retrieval_evaluation,
)
from app.services.retrieval import RankedChunk
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_test_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)
    return testing_session_local()


def test_load_retrieval_eval_dataset_reads_bundled_cases() -> None:
    dataset = load_retrieval_eval_dataset()

    assert dataset.name == "retrieval_v1"
    assert len(dataset.cases) == 6
    assert dataset.cases[0].id == "binary_search_exact_match"
    assert dataset.cases[0].documents[0].chunks[0].text.startswith("Binary search")


def test_run_retrieval_evaluation_reports_keyword_baseline_metrics() -> None:
    session = build_test_session()

    try:
        report = run_retrieval_evaluation(session)
    finally:
        session.close()

    assert report.dataset == "retrieval_v1"
    assert report.mode == "keyword"
    assert report.case_count == 6
    assert report.passed_case_count == 5
    assert report.hit_at_k == 5 / 6
    assert report.mean_reciprocal_rank == 5 / 6
    assert round(report.precision_at_k, 4) == 0.5278
    assert [case.case_id for case in report.failed_case_results] == [
        "keyword_synonym_limitation"
    ]


def test_run_retrieval_evaluation_can_run_vector_mode() -> None:
    session = build_test_session()

    try:
        report = run_retrieval_evaluation(session, mode="vector")
    finally:
        session.close()

    assert report.mode == "vector"
    assert report.case_count == 6
    assert report.passed_case_count >= 5
    assert report.hit_at_k >= 5 / 6


def test_run_retrieval_comparison_reports_all_modes() -> None:
    session = build_test_session()

    try:
        report = run_retrieval_comparison(session)
    finally:
        session.close()

    assert report.dataset == "retrieval_v1"
    assert report.case_count == 6
    assert report.modes == ["keyword", "vector", "hybrid"]
    assert set(report.mode_reports) == {"keyword", "vector", "hybrid"}
    assert report.mode_reports["keyword"].passed_case_count == 5
    assert report.mode_reports["hybrid"].hit_at_k >= report.mode_reports["keyword"].hit_at_k
    assert report.best_mode_by_hit_at_k == "keyword"
    assert report.best_mode_by_mrr == "keyword"
    assert report.best_mode_by_precision_at_k == "keyword"
    assert len(report.case_results) == 6


def test_retrieval_comparison_shows_hybrid_improves_keyword_synonym_case() -> None:
    session = build_test_session()

    try:
        report = run_retrieval_comparison(session)
    finally:
        session.close()

    synonym_case = next(
        case_result
        for case_result in report.case_results
        if case_result.case_id == "keyword_synonym_limitation"
    )

    assert not synonym_case.mode_results["keyword"].passed
    assert synonym_case.mode_results["hybrid"].passed
    assert synonym_case.mode_results["hybrid"].reciprocal_rank > 0


def test_retrieval_comparison_exposes_vector_no_match_tradeoff() -> None:
    session = build_test_session()

    try:
        report = run_retrieval_comparison(session)
    finally:
        session.close()

    no_match_case = next(
        case_result
        for case_result in report.case_results
        if case_result.case_id == "no_matching_material"
    )

    assert no_match_case.mode_results["keyword"].passed
    assert not no_match_case.mode_results["vector"].passed
    assert not no_match_case.mode_results["hybrid"].passed


def test_run_retrieval_evaluation_passes_negative_case_when_no_results_return() -> None:
    dataset = RetrievalEvalDataset(
        name="negative_case",
        cases=[
            RetrievalEvalCase(
                id="no_match",
                query="photosynthesis",
                top_k=3,
                documents=[
                    RetrievalEvalDocument(
                        filename="algorithms.txt",
                        chunks=[
                            RetrievalEvalChunk(
                                text="Stacks are last-in first-out data structures."
                            )
                        ],
                    )
                ],
                expected_results=[],
            )
        ],
    )
    session = build_test_session()

    try:
        report = run_retrieval_evaluation(session, dataset)
    finally:
        session.close()

    assert report.passed_case_count == 1
    assert report.hit_at_k == 1.0
    assert report.precision_at_k == 1.0


def test_matches_expected_result_can_require_chunk_and_page() -> None:
    returned_result = RankedChunk(
        document_id="document-id",
        document_filename="lecture.pdf",
        chunk_id="chunk-id",
        chunk_index=2,
        page_number=7,
        text="Dynamic programming stores overlapping subproblem results.",
        score=3,
        matched_terms=["dynamic", "programming"],
    )

    assert matches_expected_result(
        returned_result,
        ExpectedRetrievalResult(filename="lecture.pdf", chunk_index=2, page_number=7),
    )
    assert not matches_expected_result(
        returned_result,
        ExpectedRetrievalResult(filename="lecture.pdf", chunk_index=1, page_number=7),
    )
