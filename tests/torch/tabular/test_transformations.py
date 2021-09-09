#
# Copyright (c) 2021, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import pytest

from transformers4rec.utils.tags import Tag

pytorch = pytest.importorskip("torch")
torch4rec = pytest.importorskip("transformers4rec.torch")


@pytest.mark.parametrize("replacement_prob", [0.1, 0.3, 0.5, 0.7])
def test_stochastic_swap_noise(replacement_prob):
    NUM_SEQS = 100
    SEQ_LENGTH = 80
    PAD_TOKEN = 0

    # Creating some input sequences with padding in the end
    # (to emulate sessions with different lengths)
    seq_inputs = {
        "categ_feat": pytorch.tril(
            pytorch.randint(low=1, high=100, size=(NUM_SEQS, SEQ_LENGTH)), 1
        ),
        "cont_feat": pytorch.tril(pytorch.rand((NUM_SEQS, SEQ_LENGTH)), 1),
    }

    ssn = torch4rec.StochasticSwapNoise(pad_token=PAD_TOKEN, replacement_prob=replacement_prob)
    out_features_ssn = ssn(seq_inputs, mask=seq_inputs["categ_feat"] != PAD_TOKEN)

    for fname in seq_inputs:
        replaced_mask = out_features_ssn[fname] != seq_inputs[fname]
        replaced_mask_non_padded = pytorch.masked_select(
            replaced_mask, seq_inputs[fname] != PAD_TOKEN
        )
        replacement_rate = replaced_mask_non_padded.float().mean()
        assert replacement_rate == pytest.approx(replacement_prob, abs=0.1)


@pytest.mark.parametrize("replacement_prob", [0.1, 0.3, 0.5, 0.7])
def test_stochastic_swap_noise_with_tabular_features(
    yoochoose_schema, torch_yoochoose_like, replacement_prob
):
    PAD_TOKEN = 0

    inputs = torch_yoochoose_like
    tab_module = torch4rec.TabularSequenceFeatures.from_schema(yoochoose_schema)
    out_features = tab_module(inputs)

    ssn = torch4rec.StochasticSwapNoise(
        pad_token=PAD_TOKEN, replacement_prob=replacement_prob, schema=yoochoose_schema
    )
    out_features_ssn = tab_module(inputs, pre=ssn)

    for fname in out_features:
        replaced_mask = out_features_ssn[fname] != out_features[fname]

        # Ignoring padding items to compute the mean replacement rate
        feat_non_padding_mask = inputs[fname] != PAD_TOKEN
        # For embedding features it is necessary to expand the mask
        if len(replaced_mask.shape) > len(feat_non_padding_mask.shape):
            feat_non_padding_mask = feat_non_padding_mask.unsqueeze(-1)
        replaced_mask_non_padded = pytorch.masked_select(replaced_mask, feat_non_padding_mask)
        replacement_rate = replaced_mask_non_padded.float().mean()
        assert replacement_rate == pytest.approx(replacement_prob, abs=0.1)


@pytest.mark.parametrize("layer_norm", ["layer-norm", torch4rec.TabularLayerNorm()])
def test_layer_norm(yoochoose_schema, torch_yoochoose_like, layer_norm):
    schema = yoochoose_schema.select_by_tag(Tag.CATEGORICAL)

    emb_module = torch4rec.EmbeddingFeatures.from_schema(
        schema, embedding_dims={"item_id/list": 100}, embedding_dim_default=64, post=layer_norm
    )

    out = emb_module(torch_yoochoose_like)

    assert list(out["item_id/list"].shape) == [100, 100]
    assert list(out["category/list"].shape) == [100, 64]
