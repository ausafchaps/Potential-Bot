from app.db.base import Base
from app.evaluation.retrieval import (
    ExpectedRetrievalResult,
    RetrievalEvalCase,
    RetrievalEvalChunk,
    RetrievalEvalDataset,
    RetrievalEvalDocument,
    load_retrieval_eval_dataset,
    matches_expected_result,
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
    assert report.case_count == 6
    assert report.passed_case_count == 5
    assert report.hit_at_k == 5 / 6
    assert report.mean_reciprocal_rank == 5 / 6
    assert round(report.precision_at_k, 4) == 0.5278
    assert [case.case_id for case in report.failed_case_results] == [
        "keyword_synonym_limitation"
    ]


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
