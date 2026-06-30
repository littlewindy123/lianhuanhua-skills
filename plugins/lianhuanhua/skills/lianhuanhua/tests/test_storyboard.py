from __future__ import annotations

from lianhuanhua.storyboard import (
    DENSITY_ONE_PER_SENTENCE,
    DENSITY_SMART,
    DENSITY_THREE_SENTENCES,
    build_storyboard_data,
    group_timeline_segments,
)


def _timeline() -> dict:
    return {
        "duration": 12.0,
        "segments": [
            {"id": "seg_001", "start": 0.0, "end": 1.2, "text": "你相信吗？"},
            {"id": "seg_002", "start": 1.4, "end": 3.0, "text": "男女之间，一旦越过了界线。"},
            {"id": "seg_003", "start": 3.2, "end": 5.0, "text": "结局就会变得复杂。"},
            {"id": "seg_004", "start": 5.2, "end": 7.0, "text": "有人开始想念。"},
            {"id": "seg_005", "start": 7.2, "end": 9.0, "text": "有人开始失眠。"},
            {"id": "seg_006", "start": 9.2, "end": 12.0, "text": "最后才学会放下。"},
        ],
    }


def _project() -> dict:
    return {"video": {"width": 1080, "height": 1920, "fps": 30}}


def test_one_per_sentence_density_creates_one_shot_per_segment() -> None:
    storyboard = build_storyboard_data(
        timeline=_timeline(),
        project=_project(),
        density=DENSITY_ONE_PER_SENTENCE,
        style_prompt="手绘连环画",
    )

    assert len(storyboard["shots"]) == 6
    assert storyboard["shots"][0]["start"] == 0.0
    assert storyboard["shots"][-1]["end"] == 12.0


def test_three_sentences_density_groups_adjacent_segments() -> None:
    groups = group_timeline_segments(_timeline()["segments"], DENSITY_THREE_SENTENCES)
    storyboard = build_storyboard_data(
        timeline=_timeline(),
        project=_project(),
        density=DENSITY_THREE_SENTENCES,
    )

    assert [len(group) for group in groups] == [3, 3]
    assert len(storyboard["shots"]) == 2
    assert storyboard["shots"][0]["start"] == 0.0
    assert storyboard["shots"][0]["end"] == 5.0
    assert storyboard["shots"][1]["start"] == 5.2


def test_smart_density_generates_valid_storyboard_with_motion() -> None:
    storyboard = build_storyboard_data(
        timeline=_timeline(),
        project=_project(),
        density=DENSITY_SMART,
        style_prompt="温暖但克制",
    )

    assert 2 <= len(storyboard["shots"]) <= 6
    assert storyboard["video"]["duration"] == 12.0
    assert all(shot["image"].endswith(".png") for shot in storyboard["shots"])
    assert all(shot["motion"]["type"] for shot in storyboard["shots"])


def test_variation_strength_adds_distinct_visual_changes() -> None:
    storyboard = build_storyboard_data(
        timeline=_timeline(),
        project=_project(),
        density=DENSITY_ONE_PER_SENTENCE,
        variation_strength="明显",
    )

    cameras = {shot["camera"] for shot in storyboard["shots"]}
    backgrounds = {shot["background_change"] for shot in storyboard["shots"]}
    actions = {shot["action_change"] for shot in storyboard["shots"]}

    assert len(cameras) > 1
    assert len(backgrounds) > 1
    assert len(actions) > 1
