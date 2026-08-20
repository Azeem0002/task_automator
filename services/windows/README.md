# Windows Task Scheduler

Task Scheduler supervises the same Task Automator worker modules that Linux
systemd supervises. The worker itself stays unchanged and cross-platform.

Create one task per terminal-independent worker:

1. Open **Task Scheduler** → **Create Task**.
2. On **General**, select **Run only when user is logged on** for a local MVP.
3. On **Triggers**, add **At log on**.
4. On **Actions**, select **Start a program**.
5. Set **Program/script** to your virtual environment Python, for example:

   ```text
   C:\Users\az\task_automator\.venv\Scripts\python.exe
   ```

6. Set **Add arguments** to one of these module commands:

   ```text
   -m task_automator.workers.disk_health_monitor --path C:\Users\az --interval 60s --minimum-free-gb 1
   -m task_automator.workers.scheduled_backup C:\Users\az\Documents --interval 1h
   ```

7. Set **Start in** to the project folder, for example:

   ```text
   C:\Users\az\task_automator
   ```

8. In **Settings**, enable restart on failure and choose a bounded retry policy
   such as three restarts, one minute apart.

Do not schedule autoclear or any `WORKER_TERMINAL_BOUND = True` worker. A
scheduled task has no trustworthy interactive terminal to own.
