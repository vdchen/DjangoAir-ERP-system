# DjangoAir Check-In, Seat Selection & Boarding Policy

## Online Check-In and QR Boarding Passes
Paid passengers can complete online check-in in their Personal Cabinet to generate a downloadable PDF boarding pass containing a scannable QR code encoding their unique ticket_code (DA-XXXXXXXX).

## Interactive Seat Selection and 10-Minute Seat Holds
During booking, passengers may choose specific seats on the interactive cabin seat map. Selected seats are temporarily locked for 10 minutes (600 seconds) in Redis to prevent double-selection during checkout and released automatically if checkout is abandoned.

## Airport Gate Closure and Boarding Verification
Passengers must be checked in (`CHECKED_IN`) before arriving at the departure gate. Gate Managers scan or enter the ticket_code to register boarding (`BOARDED`). Boarding gates close 20 minutes prior to scheduled departure.
