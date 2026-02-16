"""
Lens AI — AI News Video Factory
Main entry point with 3-hour cycle scheduler.

Autonomous pipeline that scrapes 20+ reputable news sources, clusters
articles by topic, cross-references for truth vs exaggeration, and
generates punchy 9:16 short-form videos with AI voiceover and visuals.
"""

import signal
import sys
import time
from datetime import datetime

import schedule

import config
from utils.logger import log
from pipeline.orchestrator import run_cycle


# ─── Graceful Shutdown ────────────────────────────────────

_running = True


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    global _running
    log.info("\n⚠️  Shutdown signal received. Finishing current work...")
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ─── Main ─────────────────────────────────────────────────

def run_scheduled():
    """Run a single scheduled cycle with error handling."""
    try:
        stats = run_cycle()
        
        if stats["videos_generated"] > 0:
            log.info(f"🎉 Generated {stats['videos_generated']} video(s) this cycle!")
            for vp in stats["video_paths"]:
                log.info(f"   → {vp}")
        
    except Exception as e:
        log.error(f"💥 Cycle failed with unexpected error: {e}")
        import traceback
        log.error(traceback.format_exc())


def main():
    """Main entry point."""
    log.info("=" * 60)
    log.info("🔮 LENS AI — AI News Video Factory")
    log.info("=" * 60)
    log.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Cycle interval: {config.CYCLE_INTERVAL_HOURS} hours")
    log.info(f"Max videos per cycle: {config.MAX_VIDEOS_PER_CYCLE}")
    log.info(f"Output directory: {config.OUTPUT_DIR}")
    log.info(f"HF API key: {'✓ configured' if config.HF_API_KEY else '✗ MISSING'}")
    log.info("")
    
    if not config.HF_API_KEY:
        log.error("❌ No HF API key found! Set 'hff_key' in .env")
        sys.exit(1)
    
    # Handle command line args
    single_run = "--once" in sys.argv or "-1" in sys.argv
    
    if single_run:
        log.info("🔄 Running single cycle (--once mode)...")
        run_scheduled()
        log.info("✅ Single cycle complete. Exiting.")
        return
    
    # Run immediately on start
    log.info("🔄 Running initial cycle...")
    run_scheduled()
    
    # Schedule recurring cycles
    schedule.every(config.CYCLE_INTERVAL_HOURS).hours.do(run_scheduled)
    
    log.info(f"\n⏰ Scheduler active. Next cycle in {config.CYCLE_INTERVAL_HOURS} hours.")
    log.info("   Press Ctrl+C to stop.\n")
    
    while _running:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds
    
    log.info("👋 Lens AI shut down gracefully.")


if __name__ == "__main__":
    main()
