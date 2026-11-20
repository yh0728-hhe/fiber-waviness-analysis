# Download and review the analysis

Start with the repository README and professor overview; no installation or GitHub invitation is needed to read this public repository.

- [Interactive reviewer](https://github.com/yh0728-hhe/fiber-waviness-analysis/blob/main/report/review.html?raw=1): download the HTML and open it in Safari or Chrome. It is self-contained and embeds seven representative slices. This compact viewer includes automatic-QC and needs-review paths; the complete snapshot retains excluded paths.
- [Quick-review ZIP](https://github.com/yh0728-hhe/fiber-waviness-analysis/blob/main/downloads/fiber-waviness-quick-review.zip?raw=1): reviewer, selected CSV tables, figures, and interpretation notes.
- [Complete repository ZIP](https://github.com/yh0728-hhe/fiber-waviness-analysis/archive/refs/heads/main.zip): all tracked analysis outputs, all 68 derived-image sets, source code, and validation records. This is the same as Code → Download ZIP.

The full candidate table and coordinate JSON are losslessly compressed. To restore them after downloading or cloning:

```bash
python unpack_snapshot.py
```

The helper checks the original bytes against SHA-256 values. The interactive report and compact CSVs do not require unpacking or Python.

Passing automatic QC is not expert confirmation of a biological fiber. Read the validation limitations before interpreting measurements.
