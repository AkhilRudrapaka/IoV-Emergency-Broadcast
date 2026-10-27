# Collaborator Task Assignments

This document outlines the technical work distribution among the project collaborators. Each section lists specific responsibilities, associated files/modules, and starter issues (linked to GitHub issues if created later).

---

## 🌟 Akhil Rudrapaka  
- **GitHub**: [AkhilRudrapaka](https://github.com/AkhilRudrapaka)  
- **Email**: Rudrapakaakhil@gmail.com

**Primary Areas**
- Clustering logic (`clustering.py`)
- Corroboration & voting (`corroboration.py`)
- Protocol implementations (`protocols.py`, `channel.py`)
- RSU handling (`rsu.py`)

**Starter Tasks**
- Refactor clustering to support configurable cluster size.
- Add unit tests for `select_representative_cluster`.
- Optimize BLS certificate verification flow.

---

## 🎨 Charan Chandr  
- **GitHub**: [charanchandr](https://github.com/charanchandr)  
- **Email**: charanchandra616@gmail.com

**Primary Areas**
- Web interface (`web_results.py`, `results_viewer.html`)
- Static documentation portal (`portal/`)
- Front‑end UI enhancements (filters, result download).

**Starter Tasks**
- Implement a dark‑mode toggle for the results UI.
- Add pagination for large result tables.
- Fix broken links in the documentation portal.

---

## 📊 Sreeshanth Reddy  
- **GitHub**: [Sreeshanthreddy73](https://github.com/Sreeshanthreddy73)  
- **Email**: sreeshanthreddy069@gmail.com

**Primary Areas**
- Experiment orchestration (`experiment.py`)
- Metrics calculation (`metrics.py`)
- Validation suite (`validation/`)

**Starter Tasks**
- Extend `run.py experiment` to accept a JSON parameter file.
- Add new metric: average end‑to‑end latency.
- Increase CI coverage for `validation/` tests.

---

## 📚 Chakri (cb.sc.u4cse23625)  
- **GitHub**: [Chakri6325](https://github.com/Chakri6325)  
- **Email**: cb.sc.u4cse23625@cb.students.amrita.edu

**Primary Areas**
- Project documentation (`README.md`, `PROJECT_GUIDE.md`)
- AI explanation integration (`narrator.py`, `.env` handling)
- Technical writing for research reports.

**Starter Tasks**
- Update README with a quick‑start Docker section.
- Write a tutorial on enabling Groq AI explanations.
- Draft the “Limitations & Future Work” chapter.

---

## ⚙️ Alex Nikshith (cb.sc.u4cse236200)  
- **GitHub**: [alexnikshith](https://github.com/alexnikshith)  
- **Email**: cb.sc.u4cse236200@cb.students.amrita.edu

**Primary Areas**
- CI/CD pipelines (GitHub Actions)
- Build scripts (`build_portal_assets.py`, `create_portal_document.py`)
- Packaging & deployment automation.

**Starter Tasks**
- Add a GitHub Action to run `pytest` on push.
- Create a workflow to publish the static portal to GitHub Pages.
- Automate version bumping using `bump2version`.

---

## 📋 How to Contribute
1. **Create a branch** named `feature/<your‑name>/<short‑desc>`.
2. **Implement the task** listed under your name.
3. **Write tests** where applicable.
4. **Open a Pull Request** targeting `main` and assign a reviewer (preferably another collaborator).
5. **Update this file** with any new tasks or status changes.

---

> [!NOTE] Keep this file up‑to‑date. When a task is completed, mark it with `✅` and move it to a `Done` section at the bottom.
