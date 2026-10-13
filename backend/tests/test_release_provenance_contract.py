from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
PUBLISHER = ROOT / ".github" / "workflows" / "publish-current-version-on-green-main.yml"


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

    assert "gh release edit $tag --notes-file $publishedBody --draft=false --latest --target $sourceSha" in publish
    edit_i = publish.index("gh release edit $tag --notes-file $publishedBody --draft=false --latest --target $sourceSha")
    tag_i = publish.index('git/ref/tags/$tag')
    assert edit_i < tag_i
    assert "if ($tagSha -ne $sourceSha)" in publish
    assert "scripts/enrich_release_verification.ps1" in publish
    assert "-TagSha $tagSha" in publish
    assert "-ReleaseChannel $releaseChannel" in publish
    assert "-IsPrerelease $isPrerelease" in publish


def test_release_display_body_is_authoritative_before_publish() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish = _section(
        text,
        "- name: Publish verified GitHub Release",
        "- name: Upload download-back verification",
    )

    render_i = publish.index("scripts/render_published_release_body.py")
    edit_i = publish.index("gh release edit $tag --notes-file $publishedBody")
    state_i = publish.index("CHENGZHU_PUBLISHED_STATUS_BEGIN")
    assert render_i < edit_i < state_i
    assert "--source-sha" in publish
    assert "$sourceSha" in publish
    assert "--stable-latest" in publish
    assert "published Release body is missing authoritative publication truth" in publish


def test_existing_published_version_repairs_display_only_without_moving_tag() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    published = _section(
        text,
        'if [ "$is_draft" = "false" ]; then',
        'echo "$tag exists only as a draft',
    )

    assert "release_target=" in published
    assert "tag_sha=" in published
    assert 'if [ "$release_target" != "$tag_sha" ]; then' in published
    assert "scripts/render_published_release_body.py" in published
    assert 'gh release edit "$tag" --notes-file "$published_body"' in published
    assert "gh workflow run release.yml" not in published
    assert "--target" not in published
    assert "isImmutable" in published
    assert "display truth normalized; nothing to dispatch" in published


def test_release_workflow_executes_published_body_renderer_regression_on_windows() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    regression = _section(
        text,
        "- name: Published Release body regression",
        "- name: Release verification metadata regression",
    )
    assert "python @renderArgs" in regression
    assert "CHENGZHU_PUBLISHED_STATUS_BEGIN" in regression
    assert "Channel: **PRERELEASE**" in regression
    assert "underlying notes were not preserved" in regression


def test_release_verification_enrichment_supports_missing_publication_fields() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    helper = (ROOT / "scripts" / "enrich_release_verification.ps1").read_text(encoding="utf-8")
    regression = _section(
        text,
        "- name: Release verification metadata regression",
        "- name: Upload download-back verification",
    )

    # The pre-publish JSON intentionally does not contain all publication-only
    # fields. Direct assignment to a missing PSCustomObject property is exactly
    # what broke beta.3 after publication, so the helper must use Add-Member.
    assert 'Add-Member -NotePropertyName "tag_sha"' in helper
    assert 'Add-Member -NotePropertyName "release_channel"' in helper
    assert 'Add-Member -NotePropertyName "is_prerelease"' in helper
    assert "-Force" in helper
    assert "scripts/enrich_release_verification.ps1" in regression
    assert "release_channel enrichment regression" in regression


def test_download_back_evidence_is_uploaded_only_after_public_tag_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish_i = text.index("- name: Publish verified GitHub Release")
    upload_i = text.index("- name: Upload download-back verification")
    assert publish_i < upload_i


def test_generic_publisher_refuses_a_stale_green_main_sha() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")

    assert "contents: write" in text
    assert "current_main=\"$(gh api \"repos/$GITHUB_REPOSITORY/git/ref/heads/main\" --jq '.object.sha')\"" in text
    assert 'if [ "$current_main" != "$SOURCE_SHA" ]; then' in text
    assert "stale green main" in text
    assert 'if [ -f ".github/RELEASE_HOLD" ]; then' in text
    assert "release hold is active" in text
    stale_i = text.index('if [ "$current_main" != "$SOURCE_SHA" ]; then')
    hold_i = text.index('if [ -f ".github/RELEASE_HOLD" ]; then')
    dispatch_i = text.index("gh workflow run release.yml")
    assert stale_i < hold_i < dispatch_i


def test_generic_publisher_requires_committed_approval_for_unpublished_v2_stable() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    tag_i = text.index('tag="v$version"')
    published_i = text.index('if gh release view "$tag"')
    stable_i = text.index('if [[ "$version" != *-* ]]; then')
    approval_i = text.index('approval=".github/stable-release-approvals/v$version.json"')
    validate_i = text.index("scripts/v2_stable_release_approval.py validate-committed")
    dispatch_i = text.index("gh workflow run release.yml")

    assert 'if [ "$major" -ge 2 ]; then' in text
    assert "stable v2+ approval missing" in text
    assert "--release-source-sha" in text
    assert '"$SOURCE_SHA"' in text
    # Already-published immutable versions exit before approval validation;
    # only a new/draft Stable publication needs the exact-candidate approval.
    assert tag_i < published_i < stable_i < approval_i < validate_i < dispatch_i


def test_release_publish_path_rechecks_v2_stable_approval() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    version_i = text.index("- name: Release version consistency")
    approval_i = text.index("- name: Stable v2 release approval gate")
    build_i = text.index("- name: Build backend sidecar")
    publish_i = text.index("- name: Publish verified GitHub Release")

    gate = _section(
        text,
        "- name: Stable v2 release approval gate",
        "- name: License gate",
    )
    assert "scripts/v2_stable_release_approval.py validate-committed" in gate
    assert "$env:CHENGZHU_RELEASE_SOURCE_SHA" in gate
    assert "$major -ge 2" in gate
    assert "github.event.inputs.publish == 'true'" in gate
    assert version_i < approval_i < build_i < publish_i


def test_stable_approval_validator_has_candidate_parent_history_available() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    release = WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 2" in publisher
    assert "fetch-depth: 2" in release
    assert 'git", "-C", str(repo_root), "rev-parse"' not in publisher  # validator stays in Python
