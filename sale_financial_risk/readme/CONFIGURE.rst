Stored order risk uses company currency. The customer summary converts that
amount into the configured risk currency. Order-date and summary-date exchange
rate selection remain unchanged.

Upgrade to 16.0.1.1.5 to recompute existing nonzero stored risk amounts in batches.
Zero-valued rows remain unchanged because currency conversion cannot change zero.
Historical invoice-link repairs require separate review; this recomputation uses
the currently linked invoiced quantities.
