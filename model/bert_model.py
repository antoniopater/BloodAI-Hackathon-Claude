import torch
import torch.nn as nn
from transformers import BertConfig, BertModel, PreTrainedModel
from transformers.models.bert.modeling_bert import BertPreTrainedModel


LABEL_MAP = {
    "POZ": 0,
    "GASTRO": 1,
    "HEMATO": 2,
    "NEFRO": 3,
    "SOR": 4,
    "CARDIO": 5,
    "PULMO": 6,
    "HEPATO": 7,
}

REVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}
NUM_CLASSES = len(LABEL_MAP)


def get_bert_config(vocab_size: int = 500) -> BertConfig:
    """Return BERT config matching paper specifications."""
    return BertConfig(
        vocab_size=vocab_size,
        hidden_size=256,
        num_hidden_layers=6,
        num_attention_heads=8,
        intermediate_size=1024,
        hidden_act="gelu",
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1,
        max_position_embeddings=128,
        type_vocab_size=1,
        initializer_range=0.02,
        layer_norm_eps=1e-12,
        pad_token_id=0,
        position_embedding_type="absolute",
        use_cache=True,
        classifier_dropout=0.1,
    )


class BertForMultiLabelClassification(BertPreTrainedModel):
    """BERT model with multi-label classification head (sigmoid, not softmax)."""

    def __init__(self, config: BertConfig):
        super().__init__(config)
        self.num_labels = NUM_CLASSES
        self.config = config

        self.bert = BertModel(config, add_pooling_layer=False)
        self.dropout = nn.Dropout(config.classifier_dropout or config.hidden_dropout_prob)
        self.classifier = nn.Linear(config.hidden_size, NUM_CLASSES)

        self.post_init()

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        position_ids=None,
        head_mask=None,
        inputs_embeds=None,
        labels=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ):
        """
        labels: tensor of shape (batch_size, num_labels) with float values in [0, 1]
        """
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        outputs = self.bert(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            head_mask=head_mask,
            inputs_embeds=inputs_embeds,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        sequence_output = outputs[0]
        cls_output = sequence_output[:, 0, :]

        cls_output = self.dropout(cls_output)
        logits = self.classifier(cls_output)

        loss = None
        if labels is not None:
            loss_fn = nn.BCEWithLogitsLoss()
            loss = loss_fn(logits, labels)

        if not return_dict:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        from transformers.modeling_outputs import SequenceClassifierOutput

        return SequenceClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions,
        )
