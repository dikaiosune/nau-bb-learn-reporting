# nau-bb-learn-reporting
A basic tool for generating reproducible reports for Blackboard Learn 9.1. Relies on access to a Managed Hosting OpenDB account.

This tool was created to solve a very specific niche problem, but I'm sharing the code in case anyone else with the same or similar problems can make use of it.

As of May 2014, my current employer uses offsite hosting for their Blackboard Learn 9.1 instance, which means that we do not have direct access to the production database for reporting purposes. We have access to the database, but only a small number of IPs are allowed to connect to it, and so in order to run any reports, it's necessary to run an SSH proxy through on of the servers that has been whitelisted.

This tool is a very light framework for connecting to Bb Learn's Oracle database and running certain reports through an optional SSH proxy.

###Setup

1. Acquire ojdbc7.jar from Oracle, and put it in `libs/`.
2. Run the tool with the necessary configuration on the command line.

That's it! But it's actually not.

* The queries used are very much tuned for my institution's Bb Learn configuration. YMMV.
* The report format may need some munging. For ease, they are printed as tab-separated files which are then opened in Excel and manually saved to an XLSX file.

###Available Reports

* Stale "non-credit" courses report
  * To check for manually-created courses (i.e. not in the Student Information Service) courses that haven't had any activity in over a year.
* Force Completion report
  * If you use or administer Bb Learn, you know the nightmare that is Force Completion. This checks for all courses in a term that have tests with Force Completion enabled. Then, it goes and finds the exact location in the course so that the instructor can be easily notified to turn it off. See comments in `ForceCompletionReport.java` for more about the way our environment handles terms (hint it's not in the database the way you'd expect).
* SignatureAssignment report
  * This is a data integrity report for a certain set of classes that need to have certain assignments configured with certain rubrics to be able to use Blackboard's Outcomes tool in the intended way.

###Running Reports

```
Option                               Description                           
------                               -----------                           
--config <File>                      Path to properties file.              
--greedy                             Flag to make certain reports extra    
                                       detailed (currently only hardlinks).
--help                                                                     
--report-force-completion <Integer>  Find tests in a term with Force       
                                       Completion. Requires 4-digit term   
                                       code.                               
--report-hardlink-courses <Integer>  Find courses that should be checked   
                                       for hardlinks. Requires 4-digit term
                                       code.                               
--report-signature-assignments       Find rubrics and signature assignments
  <Integer>                            in COE courses. Requires 4-digit    
                                       term code.                          
--report-stale-courses               Find non-SIS courses which haven't    
                                       been accessed in over a year.  
```
###Changing Reports, Adding New Reports

Read through the source. There's nothing magical here, but it may be a convenient way to provide some structure to your institution's current SQL-based reporting, especially if you have to manually fire up an SSH tunnel every time you do it. As you can see, it's under the MIT license currently. Please attribute Northern Arizona University, as I wrote it while under their employ.
