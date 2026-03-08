# Thesis Format Adaptation Checklist

Updated: 2026-03-07

Use this checklist when moving the current draft into the official university thesis template. This file is about format adaptation, not content quality.

## 1. Front Matter

- title page follows school template exactly
- student name / ID / major / advisor fields are complete
- Chinese title and English title are both present if required
- abstract and keywords are provided in all required languages
- table of contents is auto-generated from heading styles
- list of figures is generated if the template requires it
- list of tables is generated if the template requires it

## 2. Chapter Structure

- chapter numbering matches school rules
- section numbering is consistent
- chapter opening pages follow template rules
- chapter titles in the thesis match the wording in the slide deck
- no placeholder headings remain

## 3. Figures and Tables

- every figure has a number and caption
- every table has a number and caption
- figure captions use the school-required style
- table captions use the school-required style
- all figures referenced in the text actually exist
- all tables referenced in the text actually exist
- source report paths are recorded separately even if not printed in the final thesis

## 4. Citations and References

- citation style matches school requirement
- all cited papers appear in the bibliography
- all bibliography entries are complete
- repeated references use the same key format
- official documentation references are formatted consistently
- no raw URL is left in the正文 unless the template explicitly allows it

## 5. Language and Writing Style

- abstract uses academic style, not product-pitch wording
- terms such as persona / worldline / claim attribution are translated consistently
- no first-person overuse if the school discourages it
- no exaggerated claims such as “fully solves” or “perfectly restores”
- limitations are stated explicitly
- contribution wording is consistent across abstract, introduction, conclusion, and slides

## 6. Experiment Chapter Formatting

- all metrics appear in a consistent typography style
- report file IDs are kept in internal notes, not necessarily in final正文
- baseline table matches the canonical numbers in `docs/EVAL_BASELINE.md`
- ablation table matches `docs/ABLATION_RESULTS.md`
- repeated probe figure matches `probe-variance-thesis_probe-20260307-024213-ee70482d`
- qualitative examples use the final selected case pairs

## 7. User Study Section

- if user-study data is not finished, mark it clearly as planned or ongoing
- if user-study data is finished, include:
  - participant count
  - grouping rule
  - rating dimensions
  - statistical method
  - significance statement
- questionnaire and protocol should be placed in appendix if required

## 8. Appendix and Supplementary Material

- CLI commands that matter for reproduction are moved to appendix if needed
- runbook/checklist files are referenced in appendix or supplementary material if allowed
- key evaluation commands are recorded in reproducibility appendix
- raw participant data is not embedded in the thesis body

## 9. Final Consistency Check

- thesis title matches submission system title
- abstract keywords match the Chinese and English versions
- slide deck wording does not contradict thesis wording
- contribution points in the defense match contribution points in Chapter 1
- limitation points in Chapter 5 match the spoken defense limitations

## 10. Stop Rule

Do not finalize the thesis template version until all three are true:

1. content is complete enough to survive advisor reading
2. formatting matches the school template
3. every quantitative claim can still be traced back to a real report file
