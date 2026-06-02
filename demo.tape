Output demo.gif

Require echo

Set FontSize 14
Set Width 1000
Set Height 680
Set Theme "Catppuccin Mocha"
Set Shell "bash"
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0

Hide
  Type "cd /Users/brendenarcher/Downloads/bizlang"
  Enter
  Sleep 300ms
Show

Type "python3 main.py"
Enter
Sleep 2s

Type "load sample_data/sales.csv | filter region = South | group by month | sum revenue | sort revenue desc | chart bar month revenue"
Sleep 500ms
Enter
Sleep 4s

Type "/demos"
Enter
Sleep 3s

Type "load sample_data/sales.csv | filter region = North AND units > 14 | sort revenue desc | display"
Sleep 500ms
Enter
Sleep 3s

Type "/code"
Enter
Sleep 3s

Type "/quit"
Enter
Sleep 500ms
