# IttyBitty Benchmark Report
- Structured: `True`
- max_in_tokens: `1024`, max_out_tokens: `512`, num_beams: `4`
- Models: google/flan-t5-large, facebook/bart-large-cnn, google/pegasus-pubmed

## Daniela Schiller - 2015
_File_: `C:\Users\jackc\OneDrive\Desktop\Notes\1 - Source Material\Daniela Schiller - 2015.pdf`

### Model: `google/flan-t5-large`
```text
### Abstract
Cognitive Maps of Abstract Spaces in the Hippocampus

### Introduction
Not reported

### Methods
The results also revealed that participants who showed larger hippocampal sequence.

### Results
These results are consistent with a framework that bridges theories of hippocampal function.

### Discussion
'not reported' if absent

### Synthesized (Second Pass via facebook/bart-large-cnn)
If a detail is missing, write 'not reported' Preserve numbers/units/statistics exactly as given. Avoid repetition.Combine the section summaries into a single structured abstract with exactly these headers.
```

### Model: `facebook/bart-large-cnn`
```text
### Abstract
Write a concise, factual summary of the abstract. Use ONLY facts in the text. If a detail is missing, write 'not reported' Preserve numbers/units. Avoid repetition. The most straightforward way to do this is to write the abstract in a single word.

### Introduction
Historically there have been two major views about the role of the internet in the world of medicine. This article includes an introduction and hypotheses/objectives.

### Methods
The results also revealed that participants who showed larger hippocampal sequence were more likely to live longer.

### Results
These results are consistent with a framework that bridges theories of hippocampal function.

### Discussion
No outside info. Nooretical discussions, no outside information. No discussion of the content of the article. No discussions of the contents of this article.

### Synthesized (Second Pass via facebook/bart-large-cnn)
Combine the section summaries into a single structured abstract. Use ONLY facts present in the summaries below. If a detail is missing, write 'not reported' Preserve numbers/units. Avoid repetition. Nooretical discussions, no outside information. No discussion of the content of the article.
```

### Model: `google/pegasus-pubmed`
```text
### Abstract
key clinical messagea high index of suspicion is necessary to make an early diagnosis of breast cancer in a woman. although rare, breast cancer should be considered in the differential diagnosis of any woman with a family history of the disease.

### Introduction
there are two major views about the role of navigation in medical education : the views of the expert and the commoner. the expert is the person who has the final say, whereas the commonr has to obey the rules of the game. for the expert
, there is a need to understand the facts, as well as to make recommendations.

### Methods
not reported

### Results
not reported

### Discussion
key clinical messagethis case highlights the need for a multidisciplinary approach to the treatment of chronic obstructive pulmonary disease ( copd ). we must consider not only the patient's history, but also the history of the health care provider, in order to provide the best possible care for the patient.

### Synthesized (Second Pass via facebook/bart-large-cnn)
If a detail is missing, write 'not reported' Preserve numbers/units/statistics exactly as given. Avoid repetition.Combine the section summaries into a single structured abstract with exactly these headers.
```
