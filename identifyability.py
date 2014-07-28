#!/usr/bin/python

# script for evaluating the identifyability of rows in a csv
# 
# @author: Jeff Lockhart <jlockhart@fordham.edu>

import pandas as pd
import numpy as np
from collections import defaultdict
import itertools as it
import sys, getopt
import multiprocessing as mp
from math import ceil

#global variables
g_results = []
g_n_left = []
g_rows = 0

def col_val_freq(df):
    '''
    get a dict (key = col name) of the value frequencies for each column in a data frame
    '''
    freqs = {}
    
    for c in df.columns.values:
        freqs[c] = df[c].value_counts(normalize=True)
        
    return freqs

def least_common_trait(df, idx, freqs):
    lowest_name = ""
    lowest_prob = 1
    for f in freqs:
        #this person's value for this trait is:
        val = df.loc[idx,f]
        if type(val) is str :
            if not val is "nan":
                #the likelyhood of this trait is:
                probs = freqs[f]
                likely = probs[val]
                if(likely < lowest_prob):
                    lowest_prob = likely
                    lowest_name = f
        else: #(type(val) is int or type(val) is float):
            if not np.isnan(val):
                #the likelyhood of this trait is:
                probs = freqs[f]
                likely = probs[val]
                if likely < lowest_prob:
                    lowest_prob = likely
                    lowest_name = f
    return lowest_name

def no_more_splits(f):
    can_split=True
    for k in f:
        if len(k) > 1 :
            can_split=False
            break
    
    return can_split

def gather(value):
    result, n = value
    global g_results
    global g_n_left
    g_results = g_results + result
    g_n_left = g_n_left + n

    done = len(g_n_left)
    print "Completed {:3.2f} %".format( (100.0*done)/g_rows )

    return

def batch_identify(df, pid, chunks, rows, cutoff=1):
    results = []
    nums = []
    for i in range(1, rows):
        if (i % chunks) == (pid - 1):
            r, n = identify(df, i, cutoff)
            results.append(r)
            nums.append(n)

    return results, nums

def identify(df, index, cutoff=1):
    trait_dict = {}

    #loop until the dataframe is smaller than the cutoff
    while len(df) > cutoff:
        #get frequencies of values for our current data frame
        f = col_val_freq(df)

        #see whether it's even possible to divide the rows in our data frame
        if no_more_splits(f):
            #give up if its not
            break
        
        #get the column name which is most identifying of this row
        lct = least_common_trait(df, index, f)
        #get the value that is rare
        if lct == "":
            print "error: lct is ", lct
            break
        else:
            rare_val = df.loc[index,lct]
        
            #grab the probabilities for values of this column
            probability = f[lct]
            #dave the name and probability of the value to our putput dict
            trait_dict[lct] = (rare_val, probability[rare_val])
            
            #reduce the data frame to only those rows with this rare value
            df = df[df[lct] == rare_val]
    
    #count how many folks are left in the data frame
    remaining_examples = len(df)
    
    return trait_dict, remaining_examples

def count_above_threshold(n_left, threshold):
    '''
    returns a string summary of values above the threshold
    '''
    s = "\nThreshold = " + str(threshold) + "\n"
    c = 0 #count of values above threshold
    a = 0 #average of "
    p = 0 #percent of "
    g = 0 #greatest value of n
    
    for n in n_left:
        if n > threshold:
            c = c + 1
            a = a + n
            if n > g:
                g = n
                
    if c > 0:
        a = (1.0*a) / c
    p = (100.0*c) / len(n_left)
    
    s = s + "Count above threshold = " + str(c) + "\n"
    s = s + "Percent above threshold = {:3.2f}".format(p) + "%\n"
    s = s + "Average value of those above threshold = {:3.2f}".format(a) + "\n"
    s = s + "Max value of those above threshold = " + str(g) + "\n"
    
    return s

def count_ids(id_lists):
    '''
    Return an ordered list of tuples, where the first value is the column name
    and the second value is the number of occurences
    '''
    id_counts = defaultdict(int)
    
    for ids in id_lists:
        for col_name in ids:
            id_counts[col_name] += 1
    
    sorted_c = sorted(id_counts.items(), key=lambda x:x[1], reverse=True)
    
    return sorted_c

def summarize_id_counts(counts, n_rows):
    '''
    Generate a string summary of the columns used in identification.
    '''
    s = "\nColumns used to identfy rows:\nColumn name\tPercent of rows\n"
    
    for c in counts:
        s = s + c[0] + "\t{:3.2f}".format( (100.0 * c[1]) / n_rows ) + "%\n"
    
    return s

def cols_per_row(results):
    '''
    Generate a string summary of how many columns were used to identify rows.
    '''
    s = "\nNumber of columns needed to uniquely identify a row:\n"
    n_col = []
    
    for r in results:
        n_col.append(len(r))
    
    greatest = max(n_col)
    least = min(n_col)
    ten_p = np.percentile(n_col, 10)
    q1 = np.percentile(n_col, 25)
    median = np.median(n_col)
    q3 = np.percentile(n_col, 75)
    ninty_p = np.percentile(n_col, 90)
    mean = np.mean(n_col)
    
    s = s + "Mean = {:3.2f}".format(mean) + "\n"
    s = s + "Max = " + str(greatest) + "\n"
    s = s + "Min = " + str(least) + "\n"
    s = s + "10th percentile = " + str(ten_p) + "\n"
    s = s + "25th percentile = " + str(q1) + "\n"
    s = s + "50th percentile = " + str(median) + "\n"
    s = s + "75th percentile = " + str(q3) + "\n"
    s = s + "90th percentile = " + str(ninty_p) + "\n"
    
    return s

def cols_appearing_together(results):
    '''
    Generate a string summary of columns which frequently appear together 
    in the list of columns identifying a row
    '''
    s = "\nColumns frequently used together to identify rows:\nColumn set\tFrequency\n"
    combinations = defaultdict(int)
    row_count = len(results)
    
    for r in results:
        cols = sorted(r.keys())
        comb = it.combinations(cols,2)
        for c in comb:
            combinations[c] = combinations[c] + 1
    
    sorted_c = sorted(combinations.items(), key=lambda x:x[1], reverse=True)
    
    for c in sorted_c:
        frequency = (100.0*c[1])/row_count
        if frequency > 1:
            s = s + str(c[0]) + "\t{:3.2f}".format( frequency ) + "%\n"

    return s

def usage():
    print "This script requires 4 arguments:"
    print "identifyability.py -n 4 -c 1 -i infile.csv -o outfile.txt"
    print "\t-n\tNumber of processors to use"
    print "\t-c\tCutoff: maximum number of rows in a group (usually 1)"
    print "\t-i\tA csv file to evaluate. Do not include unique id's."
    print "\t-o\tA file to print results to. Script progress is printed to stdout."
    print "\t-h\tOptional: prints this help message and exits."
    return

def main(argv):
    inputfile = ''
    outputfile = ''

    try:                                
        opts, args = getopt.getopt(argv, "hn:c:i:o:", ["help", "n_procs", "cutoff", "ifile", "ofile"])
    except getopt.GetoptError:          
        usage()                         
        sys.exit(2)                     
    if len(opts) < 4:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()                     
            sys.exit()               
        elif opt in ("-n", "--n_procs"):
            n_procs = int(arg)
        elif opt in ("-c", "--cutoff"):
            cutoff = int(arg)
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg

    print 'Reading from ', inputfile
    data = pd.read_csv(filepath_or_buffer=inputfile, low_memory=False)
    print "File has", len(data), "rows and", len(data.columns.values), "columns."

    global g_rows
    g_rows = len(data)
    results = []
    num_left = []
    pool = mp.Pool(processes=n_procs)
    #how often to gather results and print out progress
    checkpoint = 100.0
    chunks = int(ceil(g_rows/checkpoint))

    print 'Beginning identifyability checks...'
    for pid in range(1,chunks):
        pool.apply_async(batch_identify, args=(data, pid, chunks, g_rows, cutoff, ), callback=gather)
        
#        d, n = identify(data, i, cutoff)
#        results.append(d)
#        num_left.append(n)
#        if  i % 10 == 0:
#            print "Completed {:3.2f}".format( (100.0*i)/g_rows ), "% of", g_rows, "rows"
        
    pool.close()
    pool.join()

    print "Finished all rows. Writing results to", outputfile
    out = open(outputfile, 'w')
    out.write("Input file = " + inputfile + "\n")
    out.write(count_above_threshold(g_n_left, 1))
    out.write(cols_per_row(g_results))
    id_c = count_ids(g_results)
    out.write(summarize_id_counts(id_c, g_rows))
    out.write(cols_appearing_together(g_results))
    out.close()

    print "All done here."

    return


#begin execution here:
if __name__ == "__main__":
    main(sys.argv[1:])

