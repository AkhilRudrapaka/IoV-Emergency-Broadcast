# Research paper (TEA 2): check of the references marked "to be confirmed"

Manuscript: `G083_Paper.pdf` in `G083_Project_TEA_Activities.zip`, *Trust-Aware Cluster-Based Broadcast Suppression for
Real-Time Vehicular Emergency Alerts* (manuscript prepared 17 October 2026). Five references, [13] to [17], are marked
"to be confirmed". The manuscript's source file is not in the ZIP or in the project, so the PDF itself was not changed;
the corrected entries below are for the authors to paste in. Checked on 15 November 2026.

| Ref | As printed | Result | Corrected entry |
|---|---|---|---|
| [13] | Chen and Wu, 2024, clustering parameter reference cited in config.py | **Verified** (publisher page, Tech Science Press) | Q. Chen and Q. Wu, "Dynamic networking method of vehicles in VANET," *Computers, Materials & Continua*, vol. 81, no. 1, pp. 1301–1318, 2024, doi: 10.32604/cmc.2024.054799. |
| [14] | M. Trullols et al., 2010, RSU placement reference | **Verified; author initial wrong** (first author is Óscar Trullols-Cruces) | Ó. Trullols-Cruces, M. Fiore, C. Casetti, C.-F. Chiasserini, and J. M. Barceló-Ordinas, "Planning roadside infrastructure for information dissemination in intelligent transportation systems," *Computer Communications*, vol. 33, no. 4, pp. 432–442, 2010, doi: 10.1016/j.comcom.2009.11.021. |
| [15] | ETSI EN 302 636-4-1 [version to be confirmed] | **Verified: V1.4.1 (2020-01)**, the current edition. Its protocol-constants annex lists `itsGnDefaultHopLimit` = 10, the hop limit the project uses | ETSI, "Intelligent Transport Systems (ITS); Vehicular Communications; GeoNetworking; Part 4: Geographical addressing and forwarding for point-to-point and point-to-multipoint communications; Sub-part 1: Media-Independent Functionality," ETSI EN 302 636-4-1 V1.4.1, Jan. 2020. |
| [16] | ETSI TS 102 687 [version to be confirmed] | **Verified: V1.2.1 (2018-04)**. Its parameter table defines T_CBR = 100 ms as the interval over which CBR is measured, the window the project uses | ETSI, "Intelligent Transport Systems (ITS); Decentralized Congestion Control Mechanisms for Intelligent Transport Systems operating in the 5 GHz range; Access layer part," ETSI TS 102 687 V1.2.1, Apr. 2018. |
| [17] | SAE International, V2X Communications Message Set Dictionary, SAE J2735 [edition to be confirmed] | **Not verified: needs correction by the authors.** Editions exist (J2735_202007, J2735_202211, J2735_202309; SAE lists 202309, Sept. 2023, as current), but the standard is paywalled, so it could not be checked which edition supports the paper's statement (the 300-byte alert payload "scale" in `config.py` is a modelling assumption) | If kept: SAE International, "V2X Communications Message Set Dictionary," SAE J2735_202309, Sept. 2023, **only if** that is the edition the team consulted; otherwise describe the 300-byte payload as an assumption and drop the citation. |

Sources: Tech Science Press (CMC 81(1), 2024); DBLP and Scilit records for Computer Communications 33(4) and DOI
10.1016/j.comcom.2009.11.021; the ETSI PDFs of EN 302 636-4-1 V1.4.1 and TS 102 687 V1.2.1 (text searched);
SAE Mobilus listings of J2735_202007 and J2735_202309.
