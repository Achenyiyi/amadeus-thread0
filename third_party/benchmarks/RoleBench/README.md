---
language: 
- zh
- en
pretty_name: "RoleBench"
tags:
- Role-Playing
- Instruction
license: "apache-2.0"

---

# RoleBench

- Paper Title: RoleLLM: Benchmarking, Eliciting, and Enhancing Role-Playing Abilities of Large Language Models
- arXiv Link: https://arxiv.org/abs/2310.00746
- Github Repo: https://github.com/InteractiveNLP-Team/RoleLLM-public

Please read our paper for more details about this dataset.

TL;DR: We introduce RoleLLM, a role-playing framework of data construction and evaluation (RoleBench), as well as solutions for both closed-source and open-source models (RoleGPT, RoleLLaMA, RoleGLM). We also propose Context-Instruct for long-text knowledge extraction and role-specific knowledge injection.

---

# List of Roles

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/rolellm-bird-eye.png)

Abraham Lincoln, Alvy Singer, Andrew Detmer, Angel, Antonio Salieri, Bai Li (李白，Chinese), Benjamin Button, Blair Waldorf, Bruno Antony, Caden Cotard, Caesar, Coach Eric Taylor, Colonel Hans Landa, Colonel Nathan R. Jessep, Coriolanus, D_Artagnan, David Aames, Doctor Who, Dr. Frank N Furter, Dr. Hannibal Lecter, Emperor (《甄嬛传》皇帝，Chinese), Fei Zhang (张飞，Chinese), Fletcher Reede, Frank T.J. Mackey, Fred Flintstone, Freddy Krueger, Gaston, Gregory House, HAL 9000, Harvey Milk, Imperial Concubine Hua (《甄嬛传》华妃，Chinese), Jack, Jack Sparrow, Jack Torrance, Jackie Moon, James Bond, James Brown, James Carter, Jeff Spicoli, Jigsaw, Jim Morrison, John Coffey, John Dillinger, John Doe, John Keating, Jordan Belfort, Judge Dredd, Judy Hoops, Juno MacGuff, Karl Childers, Klaus Mikaelson, Leonard Shelby, Leroy Jethro Gibbs, Lestat de Lioncourt, Logan, Lucifer Morningstar, Lyn Cassady, Malcolm X, Mark Renton, Mary Sibley, Mater, Michael Scott, Murphy MacManus, Oliver Queen, Pat Solitano, Paul Conroy, Paul Vitti, Peter Parker, Po, Professor G.H. Dorr, Queen Catherine, Queen Elizabeth I, Rachel Lang, Randle McMurphy, Raylan Givens, Robert Angier, Rorschach, Seth, Sheldon Cooper, Sherlock Holmes, Shrek, Sonny, Stanley Ipkiss, Stephen Hawking, Stifler, The Dude, Theodore Twombly, Thor, Tom Ripley, Travis Bickle, Truman Capote, Tugg Speedman, Twilight Sparkle, Tyler Hawkins, Tyrion Lannister, Violet Weston, Wade Wilson, Walt Kowalski, Willie Soke, Wukong Sun (《西游记》孙悟空，Chinese).

---

# Non-Cherry-Picked Demonstrations

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/wukong-demo.png)

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/twilight-demo.png)

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/jack_sparrow-demo.png)

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/hawking-demo.png)

---

# Statistics

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/statistics-1.png)

![](https://github.com/InteractiveNLP-Team/RoleLLM-public/raw/main/assets/statistics-2.png)


---

# Download

```bash
git lfs install
git clone https://huggingface.co/datasets/ZenMoore/RoleBench
```

```python
from datasets import load_dataset

dataset = load_dataset("ZenMoore/RoleBench")
```

---

# File Structure

- `instructions-eng`: Contains English Instructions (both general and role-specific ones). `nums.jsonl` indicates the number of role-specific instructions for each role, while `split_info.txt` records how many segments each role's script can be divided into during the Context-Instruct.
- `instructions-zh`: Similarly for Chinese.
- `profiles-eng`: Contains the description file `desc.json` for all roles, dialogue data files `profiles-eng-{role_name}.jsonl` for each role, and the script names in `scripts.json`.
- `profiles-zh`: Similarly for Chinese.
- `rolebench-eng/instruction-generalization`, `rolebench-eng/role-generalization`, and `rolebench-zh`: All contain two subfolders: `general` and `role_specific`. Each subfolder has training data, testing data, and the RoleGPT baseline results for comparison.

---

# License

Apache 2.0 License.

---

# Citation

Feel free to cite us if you like RoleBench and RoleLLM.

```bibtex
@article{wang2023rolellm,
  title   = {RoleLLM: Benchmarking, Eliciting, and Enhancing Role-Playing Abilities of Large Language Models},
  author  = {Zekun Moore Wang and Zhongyuan Peng and Haoran Que and Jiaheng Liu and Wangchunshu Zhou and Yuhan Wu and Hongcheng Guo and Ruitong Gan and Zehao Ni and Man Zhang and Zhaoxiang Zhang and Wanli Ouyang and Ke Xu and Wenhu Chen and Jie Fu and Junran Peng},
  year    = {2023},
  journal = {arXiv preprint arXiv: 2310.00746}
}
```

```bibtex
@article{wang2023interactive,
  title={Interactive Natural Language Processing},
  author={Wang, Zekun and Zhang, Ge and Yang, Kexin and Shi, Ning and Zhou, Wangchunshu and Hao, Shaochun and Xiong, Guangzheng and Li, Yizhi and Sim, Mong Yuan and Chen, Xiuying and others},
  journal={arXiv preprint arXiv:2305.13246},
  year={2023}
}
```