# PARAMETER TUNING REPORT SUGGESTIONS 

For the actual irace main race:

  - Started: August 28 at 18:42:32 CST
  - Interrupted: around 19:23:02
  - Recovery started: around 19:29:23
  - Interruption gap: approximately 6 minutes 21 seconds
  - All 2,000 evaluations finished: 22:17:00
  - Final irace files completed: 22:18:10
  - End-to-end wall time: 3 hours 35 minutes 38 seconds, including the
    interruption and finalization

  - Estimated active wall time: approximately 3 hours 29 minutes
  - Summed target-runner time: 10 hours 8 minutes 13 seconds across four
    parallel workers

  The saved recovered irace object independently reports 2 hours 47 minutes 38
  seconds for the recovery session, which agrees with the file timestamps.

  The later full-budget survivor stage was separate:

  - Approximately 22:18 to 03:11
  - Wall time: approximately 4 hours 53 minutes
  - Summed worker-time: 18 hours 23 minutes across four workers
  - Runs: five configurations × four arms × ten seeds = 200

  Therefore:

  - “irace main race” = approximately 3.6 wall-clock hours.
  - “complete hyperparameter selection, including full-budget survivor
    validation” = approximately 8 hours 29 minutes end to end.

  - Combined summed worker-time = approximately 28.53 hours.

  For the paper, I would write:

  > The irace main race completed 2,000 target evaluations in approximately
  > 3.6 hours of elapsed wall-clock time using four parallel workers,
  > corresponding to 10.14 summed worker-hours. Including the subsequent 200
  > full-budget survivor runs, the complete hyperparameter-selection procedure
  > required approximately 8.5 hours of elapsed wall time.

  These are reconstructed from preserved timestamps and internal elapsed-time
  records, so they are considerably stronger than simply saying “around five
  hours.” No files were modified.
