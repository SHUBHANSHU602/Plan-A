# Architecture

Plan-A separates model inference from operational decision logic.

```text
environmental features -> ML inference -> risk service -> exposure lookup
                                                |
                                                v
                                      alert policy and deduplication
                                                |
                                                v
                                    dashboard and notification adapters
```

The ML layer owns probability, predicted class, and explanation drivers. The
backend owns persistence, risk levels, exposure, alert rules, deduplication,
notification delivery, and the human acknowledgement lifecycle.
