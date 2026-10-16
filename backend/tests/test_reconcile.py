"""Reconciliação das duas leituras (spec reading-reconciliation, design D7). Leitores falsos."""

from app.models.document import ILLEGIBLE, BBox, ReadingSource, ResolvedBy, WordStatus
from app.pipeline.reading import ReadWord
from app.pipeline.reconcile import matches, reconcile_block

BLIND = frozenset("ªº—–“”")


def paddle(text: str, x: float, y: float = 0, w: float = 80, conf: float = 0.97) -> ReadWord:
    return ReadWord(text, BBox(x=x, y=y, w=w, h=20), conf, ReadingSource.PADDLE)


def doctr(text: str, x: float, y: float = 0, w: float = 80, conf: float = 0.97) -> ReadWord:
    return ReadWord(text, BBox(x=x, y=y, w=w, h=20), conf, ReadingSource.DOCTR)


def no_reread(bbox: BBox) -> tuple[str, str]:
    return ("", "x")


class TestAgreement:
    def test_equal_readings_are_accepted(self) -> None:
        [word] = reconcile_block([paddle("contrato", 0)], [doctr("contrato", 2)], BLIND, "b0")
        assert (word.text, word.status, word.resolved_by) == (
            "contrato",
            WordStatus.ACCEPTED,
            None,
        )
        assert word.id == "b0w0"

    def test_literal_transcription_keeps_typos(self) -> None:
        [word] = reconcile_block([paddle("excessão", 0)], [doctr("excessão", 0)], BLIND, "b0")
        assert word.text == "excessão"

    def test_word_split_by_one_reader_is_compared_as_a_whole(self) -> None:
        words = reconcile_block(
            [paddle("CONTRATO", 0, w=160)],
            [doctr("CONTRA", 0, w=120), doctr("TO", 122, w=38)],
            BLIND,
            "b0",
        )
        assert [(w.text, w.status) for w in words] == [("CONTRATO", WordStatus.ACCEPTED)]
        assert words[0].bbox == BBox(x=0, y=0, w=160, h=20)

    def test_quotes_and_dashes_are_equivalent_and_paddle_spelling_is_kept(self) -> None:
        [word] = reconcile_block([paddle("“Lei”", 0)], [doctr('"Lei"', 0)], BLIND, "b0")
        assert (word.text, word.status) == ("“Lei”", WordStatus.ACCEPTED)

    def test_characters_unknown_to_doctr_do_not_count_as_divergence(self) -> None:
        words = reconcile_block(
            [paddle("1ª", 0), paddle("nº", 100)],
            [doctr("13", 0), doctr("n", 100)],
            BLIND,
            "b0",
        )
        assert [(w.text, w.status) for w in words] == [
            ("1ª", WordStatus.ACCEPTED),
            ("nº", WordStatus.ACCEPTED),
        ]

    def test_lone_dash_only_paddle_can_read_is_accepted(self) -> None:
        words = reconcile_block(
            [paddle("123", 0), paddle("—", 100, w=30), paddle("R$", 150)],
            [doctr("123", 0), doctr("R$", 150)],
            BLIND,
            "b0",
        )
        assert [(w.text, w.status) for w in words] == [
            ("123", WordStatus.ACCEPTED),
            ("—", WordStatus.ACCEPTED),
            ("R$", WordStatus.ACCEPTED),
        ]

    def test_text_made_only_of_characters_doctr_cannot_read_ignores_its_reading(self) -> None:
        [word] = reconcile_block(
            [paddle("—", 0, conf=0.95)], [doctr("_`{|}", 0, conf=1.0)], BLIND, "b0"
        )
        assert (word.text, word.status) == ("—", WordStatus.ACCEPTED)

    def test_spaces_seen_by_doctr_are_kept(self) -> None:
        words = reconcile_block(
            [paddle("R$17,00", 0, w=160), paddle("1×Mochila", 0, y=40, w=200)],
            [
                doctr("R$", 0, w=40),
                doctr("17,00", 60, w=100),
                doctr("1x", 0, y=40, w=40),
                doctr("Mochila", 60, y=40, w=140),
            ],
            BLIND | {"×"},
            "b0",
        )
        assert [(w.text, w.status) for w in words] == [
            ("R$ 17,00", WordStatus.ACCEPTED),
            ("1× Mochila", WordStatus.ACCEPTED),
        ]

    def test_paddle_words_keep_their_spaces_even_if_boxes_overlap(self) -> None:
        [word] = reconcile_block(
            [paddle("pagará", 0, w=170), paddle("à", 110, w=60)],
            [doctr("pagará", 0, w=130), doctr("à", 132, w=30)],
            BLIND,
            "b0",
        )
        assert word.text == "pagará à"

    def test_degree_sign_right_after_a_letter_is_the_ordinal_indicator(self) -> None:
        words = reconcile_block(
            [paddle("n°", 0), paddle("N°", 100), paddle("25°C", 200)],
            [doctr("n°", 0), doctr("N°", 100), doctr("25°C", 200)],
            BLIND,
            "b0",
        )
        assert [w.text for w in words] == ["nº", "Nº", "25°C"]
        assert [a.text for a in words[0].alternatives] == ["nº"]

    def test_ordinal_fix_also_applies_to_rereading(self) -> None:
        [word] = reconcile_block(
            [paddle("n°", 0, conf=0.8)],
            [doctr("m", 0, conf=0.8)],
            BLIND,
            "b0",
            lambda b: ("n°", "nº"),
        )
        assert (word.text, word.resolved_by) == ("nº", ResolvedBy.REREAD)

    def test_known_characters_still_must_match(self) -> None:
        assert matches("1ª", "13", BLIND)
        assert not matches("1a", "13", BLIND)
        assert not matches("Silva", "Silvia", BLIND)


class TestResolution:
    def test_resolved_by_confidence(self) -> None:
        [word] = reconcile_block(
            [paddle("150", 0, conf=0.97)], [doctr("15O", 0, conf=0.71)], BLIND, "b0", no_reread
        )
        assert (word.text, word.status, word.resolved_by) == (
            "150",
            WordStatus.RESOLVED,
            ResolvedBy.CONFIDENCE,
        )

    def test_confident_secondary_reading_also_wins(self) -> None:
        [word] = reconcile_block(
            [paddle("Sllva", 0, conf=0.62)], [doctr("Silva", 0, conf=0.95)], BLIND, "b0"
        )
        assert (word.text, word.resolved_by) == ("Silva", ResolvedBy.CONFIDENCE)

    def test_confidence_rule_needs_both_margin_and_floor(self) -> None:
        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.88)], [doctr("Sllva", 0, conf=0.50)], BLIND, "b0"
        )
        assert word.status is WordStatus.UNCERTAIN

    def test_resolved_by_reread(self) -> None:
        seen: list[BBox] = []

        def reread(bbox: BBox) -> tuple[str, str]:
            seen.append(bbox)
            return ("Silva", "Silva")

        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.90)],
            [doctr("Sllva", 0, conf=0.85)],
            BLIND,
            "b0",
            reread,
        )
        assert (word.text, word.status, word.resolved_by) == (
            "Silva",
            WordStatus.RESOLVED,
            ResolvedBy.REREAD,
        )
        assert seen == [BBox(x=0, y=0, w=80, h=20)]

    def test_without_arbiter_divergence_stays_uncertain_with_best_reading(self) -> None:
        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.80)],
            [doctr("Sllva", 0, conf=0.85)],
            BLIND,
            "b0",
            no_reread,
        )
        assert (word.text, word.status) == ("Sllva", WordStatus.UNCERTAIN)
        assert [(a.text, a.confidence, a.source) for a in word.alternatives] == [
            ("Sllva", 0.85, ReadingSource.DOCTR),
            ("Silva", 0.80, ReadingSource.PADDLE),
        ]

    def test_arbiter_choice_among_alternatives_resolves(self) -> None:
        asked: list[list[str]] = []

        def arbiter(bbox: BBox, options: list[str]) -> str | None:
            asked.append(options)
            return "Silva"

        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.80)],
            [doctr("Sllva", 0, conf=0.85)],
            BLIND,
            "b0",
            no_reread,
            arbiter,
        )
        assert (word.text, word.resolved_by) == ("Silva", ResolvedBy.ARBITER)
        assert asked == [["Sllva", "Silva"]]

    def test_arbiter_inventing_text_is_discarded(self) -> None:
        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.80)],
            [doctr("Sllva", 0, conf=0.85)],
            BLIND,
            "b0",
            no_reread,
            lambda bbox, options: "Silveira",
        )
        assert (word.text, word.status) == ("Sllva", WordStatus.UNCERTAIN)

    def test_arbiter_saying_illegible_marks_the_word_illegible(self) -> None:
        [word] = reconcile_block(
            [paddle("Silva", 0, conf=0.80)],
            [doctr("Sllva", 0, conf=0.85)],
            BLIND,
            "b0",
            no_reread,
            lambda bbox, options: ILLEGIBLE,
        )
        assert (word.text, word.status) == (ILLEGIBLE, WordStatus.UNCERTAIN)
        assert len(word.alternatives) == 2


class TestUnpairedWords:
    def test_word_only_one_reader_saw_with_low_confidence_is_uncertain(self) -> None:
        words = reconcile_block(
            [paddle("de", 0), paddle("ilha", 100, conf=0.6)],
            [doctr("de", 0)],
            BLIND,
            "b0",
            no_reread,
        )
        assert [(w.text, w.status) for w in words] == [
            ("de", WordStatus.ACCEPTED),
            ("ilha", WordStatus.UNCERTAIN),
        ]
        assert [a.text for a in words[1].alternatives] == ["ilha", ""]

    def test_confident_word_only_one_reader_saw_is_resolved(self) -> None:
        [word] = reconcile_block([], [doctr("anexo", 0, conf=0.96)], BLIND, "b0", no_reread)
        assert (word.text, word.resolved_by) == ("anexo", ResolvedBy.CONFIDENCE)

    def test_nothing_read_gives_no_words(self) -> None:
        assert reconcile_block([], [], BLIND, "b0") == []


def test_words_come_out_in_reading_order() -> None:
    primary = [paddle("três", 0, y=40), paddle("dois", 100, y=1), paddle("um", 0, y=0)]
    secondary = [doctr("um", 0, y=0), doctr("três", 0, y=41), doctr("dois", 100, y=2)]
    words = reconcile_block(primary, secondary, BLIND, "b0")
    assert [w.text for w in words] == ["um", "dois", "três"]
    assert [w.id for w in words] == ["b0w0", "b0w1", "b0w2"]


def test_accepted_words_keep_both_source_readings() -> None:
    [word] = reconcile_block([paddle("1ª", 0, conf=0.9)], [doctr("13", 0, conf=0.7)], BLIND, "b0")
    assert [(a.text, a.source) for a in word.alternatives] == [
        ("1ª", ReadingSource.PADDLE),
        ("13", ReadingSource.DOCTR),
    ]
