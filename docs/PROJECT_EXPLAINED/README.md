# TerraMind: implementation explained

This guide describes the actual foundations worktree, based on commit `01bf4942174dfb2b1fac9fe57e841a07bd4b3716`. Foundations changes remain uncommitted; this is not a release or a deployment. Start with the architecture, then follow the numbered chapters. The implementation inventory and detailed evidence are in [FOUNDATIONS_VERIFICATION](../FOUNDATIONS_VERIFICATION.md), [capability report](../FOUNDATIONS_REPORT.md) and [Windows review](../WINDOWS_FOUNDATIONS_REVIEW.md).

Evidence labels matter: **automated/mock** verifies deterministic behavior and contracts; **live environmental** verifies actual Open-Meteo responses; **rule demonstration** is explicitly labelled and does not verify trained inference. Genuine Windows checkpoint inference and Groq explanations remain pending for this foundation version. Historical model-card results are not newly verified accuracy claims.

## Chapters

1. [Vision and scope](01_VISION_SCOPE.md)
2. [Architecture and lifecycle](02_ARCHITECTURE_LIFECYCLE.md)
3. [Trained NLP](03_TRAINED_NLP.md)
4. [Grounded GenAI](04_GROUNDED_GENAI.md)
5. [Environmental data and locations](05_ENVIRONMENTAL_DATA.md)
6. [Analytics and formulas](06_ANALYTICS_FORMULAS.md)
7. [React, real map and Inspector](07_REACT_MAP_INSPECTOR.md)
8. [FastAPI endpoints](08_FASTAPI_ENDPOINTS.md)
9. [Streamlit and dependencies](09_STREAMLIT_TECHNOLOGIES.md)
10. [Verification, limitations and future work](10_TESTING_LIMITATIONS.md)
11. [60 technical viva questions and answers](11_VIVA_QUESTIONS.md)
12. [Six-minute demonstration](12_DEMONSTRATION.md)
13. [Git and Windows handover](13_WINDOWS_GIT_HANDOVER.md)
