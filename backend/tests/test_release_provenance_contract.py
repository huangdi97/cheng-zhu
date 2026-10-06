from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _section(text: str, start: str, end: str | None = None) -> str:
    i = text.index(start)
    if end is None:
        return text[i:]
    j = text.index(end, i + len(start))
    return text[i:j]


def test_draft_release_does_not_require_a_git_tag_before_publish() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    create = _section(
        text,
        "- name: Create draft GitHub Release for verification",
        "- name: Download-back verification",
    )
    download = _section(
        text,
        "- name: Download-back verification",
        "- name: Publish verified GitHub Release",
    )

    assert "gh release create $tag" in create
    assert "--target $sourceSha" in create
    assert "--draft" in create
    assert "--json targetCommitish" in create
    assert "git/ref/tags/$tag" not in create

    # A draft release has no refs/tags/<tag> yet. Download-back must therefore
    # validate the draft's targetCommitish rather than a non-existent git ref.
    assert "--json targetCommitish,isDraft" in download
    assert "git/ref/tags/$tag" not in download


def test_publication_materializes_and_verifies_the_exact_tag_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish = _section(
        text,
        "- name: Publish verified GitHub Release",
        "- name: Upload download-back verification",
    )

    assert "gh release edit $tag --draft=false --latest --target $sourceSha" in publish
    edit_i = publish.index("gh release edit $tag --draft=false --latest --target $sourceSha")
    tag_i = publish.index('git/ref/tags/$tag')
    assert edit_i < tag_i
    assert "if ($tagSha -ne $sourceSha)" in publish
    assert "$verification.tag_sha = $tagSha" in publish


def test_download_back_evidence_is_uploaded_only_after_public_tag_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish_i = text.index("- name: Publish verified GitHub Release")
    upload_i = text.index("- name: Upload download-back verification")
    assert publish_i < upload_i
