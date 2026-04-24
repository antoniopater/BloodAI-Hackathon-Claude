#!/bin/bash
# Watchdog — monitoruje fine-tuning, auto-restart z ostatniego checkpointu

PROJ="/Users/antonio/ClaudeHackathon-Repo /BloodAI-Hackathon-Claude"
LOG="/tmp/finetune.log"
PIDFILE="/tmp/finetune.pid"
CHECK_INTERVAL=60

start_training() {
    cd "$PROJ"
    nohup caffeinate -i env \
        USE_TF=0 \
        PYTHONPATH="$PROJ" \
        python model/finetune_multilabel.py \
            --pretrained checkpoints/mlm \
            --train-corpus data/train.txt \
            --val-corpus data/val.txt \
            --output checkpoints/finetune \
            --epochs 5 \
            --batch-size 32 \
            --lr 2e-5 \
            --focal-gamma 2.0 \
        >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[$(date '+%H:%M:%S')] Uruchomiono trening, PID: $!" | tee -a "$LOG"
}

echo "[$(date '+%H:%M:%S')] Watchdog startuje" | tee -a "$LOG"

# Zabij stary proces jeśli istnieje
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    kill "$OLD_PID" 2>/dev/null
fi

start_training

while true; do
    sleep $CHECK_INTERVAL
    PID=$(cat "$PIDFILE" 2>/dev/null)

    if [ -z "$PID" ] || ! ps -p "$PID" > /dev/null 2>&1; then
        # Sprawdź czy trening się normalnie zakończył
        if grep -q "Fine-tuning complete" "$LOG" 2>/dev/null; then
            echo "[$(date '+%H:%M:%S')] Trening zakończony pomyślnie. Watchdog kończy pracę." | tee -a "$LOG"
            exit 0
        fi

        echo "[$(date '+%H:%M:%S')] Proces padł — restartuję z ostatniego checkpointu..." | tee -a "$LOG"
        start_training
    fi
done
