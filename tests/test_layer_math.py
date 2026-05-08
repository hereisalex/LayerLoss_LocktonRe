"""Unit tests for src.layer_math — per-claim cession calculations."""

import pytest

from src.layer_math import clamp, compute_cession_pre_aal


# ── clamp() ─────────────────────────────────────────────────────────────

class TestClamp:
    def test_value_within_bounds(self):
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_value_below_lower_bound(self):
        assert clamp(-3.0, 0.0, 10.0) == 0.0

    def test_value_above_upper_bound(self):
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_value_equals_lower_bound(self):
        assert clamp(0.0, 0.0, 10.0) == 0.0

    def test_value_equals_upper_bound(self):
        assert clamp(10.0, 0.0, 10.0) == 10.0


# ── excluded treatment ──────────────────────────────────────────────────

class TestExcluded:
    def test_loss_below_attachment(self):
        """Loss doesn't reach the layer — cession is zero."""
        result = compute_cession_pre_aal(
            loss=500_000, alae=100_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="excluded",
        )
        assert result == 0.0

    def test_loss_within_layer(self):
        """Loss partially fills the layer."""
        result = compute_cession_pre_aal(
            loss=1_500_000, alae=200_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="excluded",
        )
        assert result == 500_000.0

    def test_loss_exceeds_limit(self):
        """Loss exceeds layer — capped at limit."""
        result = compute_cession_pre_aal(
            loss=5_000_000, alae=500_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="excluded",
        )
        assert result == 1_000_000.0

    def test_alae_ignored(self):
        """ALAE has zero effect on excluded treatment."""
        no_alae = compute_cession_pre_aal(
            loss=2_000_000, alae=0,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="excluded",
        )
        big_alae = compute_cession_pre_aal(
            loss=2_000_000, alae=10_000_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="excluded",
        )
        assert no_alae == big_alae

    def test_zero_loss(self):
        result = compute_cession_pre_aal(
            loss=0, alae=500_000,
            attachment=0, limit=1_000_000,
            alae_treatment="excluded",
        )
        assert result == 0.0

    def test_sanity_check_1_L3(self):
        """Sanity check #1 — L3: loss=4M, attachment=5M → 0."""
        result = compute_cession_pre_aal(
            loss=4_000_000, alae=500_000,
            attachment=5_000_000, limit=5_000_000,
            alae_treatment="excluded",
        )
        assert result == 0.0


# ── pro_rata treatment ──────────────────────────────────────────────────

class TestProRata:
    def test_loss_below_attachment(self):
        result = compute_cession_pre_aal(
            loss=500_000, alae=100_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="pro_rata",
        )
        assert result == 0.0

    def test_partial_layer_fill(self):
        """ALAE follows proportionally with the loss."""
        result = compute_cession_pre_aal(
            loss=2_000_000, alae=200_000,
            attachment=1_000_000, limit=2_000_000,
            alae_treatment="pro_rata",
        )
        # loss_in_layer = clamp(1M, 0, 2M) = 1M
        # alae_in_layer = 200K * (1M/2M) = 100K
        # total = 1.1M
        assert result == pytest.approx(1_100_000.0)

    def test_zero_loss_with_alae(self):
        """When loss=0, pro_rata ALAE should be 0 (no division by zero)."""
        result = compute_cession_pre_aal(
            loss=0, alae=500_000,
            attachment=0, limit=1_000_000,
            alae_treatment="pro_rata",
        )
        assert result == 0.0

    def test_sanity_check_1_L1(self):
        """Sanity check #1 — L1: loss=4M, alae=500K, att=1M, lim=1M → 1,125,000."""
        result = compute_cession_pre_aal(
            loss=4_000_000, alae=500_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="pro_rata",
        )
        # loss_in_layer = clamp(3M, 0, 1M) = 1M
        # alae_in_layer = 500K * (1M / 4M) = 125K
        # total = 1.125M
        assert result == pytest.approx(1_125_000.0)

    def test_full_layer_fill(self):
        """Loss fills layer exactly."""
        result = compute_cession_pre_aal(
            loss=3_000_000, alae=300_000,
            attachment=1_000_000, limit=2_000_000,
            alae_treatment="pro_rata",
        )
        # loss_in_layer = clamp(2M, 0, 2M) = 2M
        # alae_in_layer = 300K * (2M/3M) = 200K
        # total = 2.2M
        assert result == pytest.approx(2_200_000.0)


# ── part_of treatment ──────────────────────────────────────────────────

class TestPartOf:
    def test_ground_up_below_attachment(self):
        result = compute_cession_pre_aal(
            loss=500_000, alae=100_000,
            attachment=1_000_000, limit=1_000_000,
            alae_treatment="part_of",
        )
        assert result == 0.0

    def test_ground_up_within_layer(self):
        result = compute_cession_pre_aal(
            loss=1_500_000, alae=500_000,
            attachment=1_000_000, limit=2_000_000,
            alae_treatment="part_of",
        )
        # ground_up = 2M, clamp(2M - 1M, 0, 2M) = 1M
        assert result == 1_000_000.0

    def test_ground_up_exceeds_limit(self):
        result = compute_cession_pre_aal(
            loss=5_000_000, alae=1_000_000,
            attachment=1_000_000, limit=2_000_000,
            alae_treatment="part_of",
        )
        # ground_up = 6M, clamp(5M, 0, 2M) = 2M
        assert result == 2_000_000.0

    def test_sanity_check_1_L2(self):
        """Sanity check #1 — L2: loss=4M, alae=500K, att=2M, lim=3M → 2,500,000."""
        result = compute_cession_pre_aal(
            loss=4_000_000, alae=500_000,
            attachment=2_000_000, limit=3_000_000,
            alae_treatment="part_of",
        )
        # ground_up = 4.5M, clamp(2.5M, 0, 3M) = 2.5M
        assert result == pytest.approx(2_500_000.0)

    def test_zero_loss_nonzero_alae(self):
        """ALAE alone can push through the layer in part_of."""
        result = compute_cession_pre_aal(
            loss=0, alae=2_000_000,
            attachment=1_000_000, limit=3_000_000,
            alae_treatment="part_of",
        )
        # ground_up = 2M, clamp(1M, 0, 3M) = 1M
        assert result == 1_000_000.0


# ── invalid treatment ──────────────────────────────────────────────────

class TestInvalidTreatment:
    def test_unknown_treatment_raises(self):
        with pytest.raises(ValueError, match="Unknown alae_treatment"):
            compute_cession_pre_aal(
                loss=1_000_000, alae=0,
                attachment=0, limit=1_000_000,
                alae_treatment="invalid_type",
            )
