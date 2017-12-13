### Read 
![Read Operation](SearchIndex/assets/read_operation.png)  

1. Incoming request is sent to API gateway.
2. API gateway triggers first lambda.
3. First lambda retrieves partition URIs for given tokens from the INDEX_PARTITION_METADATA table.
4. First lambda posts a record with to kinesis stream for each partition.
5. Kinesis stream triggers second lambda for each partition.
6. Second lambda retrieves partition from S3 bucket.
7. Second lambda posts result to SQS.
8. First lambda retrieves messages by group ID from SQS and combines results.
9. API gateway captures lambda return and sends response.

Read is the core function of the index, and as such this needs to be a quick
operation. Fortunately, partitioning our index enables asynchronous parallel
searches to be run for sets of tokens. In order to launch async searches of
different partitions we will make use of AWS Lambda. Searches will begin with
a REST call to an API Gateway that trigger a Lambda. This first lambda is
responsible for deconstructing the invocation and determining which index partitions
should be searched. The input for this call should simply be JSON containing
the tokens to be queried.

```javascript
{
  tokens: [string]
}
```

Once this has been determined, the Lambda posts records to a kinesis stream which
will trigger asynchronous Lambdas to process their given partitions. The documents
posted to kinesis, and thus the inputs for the second Lambdas will be of this format:

```javascript
{
  partitionURIs: [string],
  searchTokens: [string],
  queryID: string
}
```

These intermediary Lambdas will retrieve the partitions they need to search from S3,
search for their specified tokens, and relay the results to an aggregator via SQS. The
message sent to the aggregator will be of this format:

```javascript
{
  tokens: [
    {
      token: string,
      ngramSize: int,
      documentOccurences: [
        {
          documentID: string,
          lockNo: int,
          locations: [int]
        }
      ]
    }
  ],
  queryID: string
}
```
Note that the queryID is the SQS messageGroupID.

The aggregator is responsible for combining the results of the parallel
searches and resolving any consistency issues. This is done by ensuring that
if multiple tokens match to the same document, the returned values must be for
the correct lockNo. If the lockNo differs then the search is repeated for those
specific tokens. Once the results have been combined, the aggregator retrieves
document metadata for the resulting documents. Once again, the aggregator will
compare the lockNo of the document and re-launch queries for tokens that appeared
in a given document if there is a mismatch. If a document has been deleted while
a read was in progress, tokens for the deleted document will be discarded from
the results sent to the aggregator. Once all documents have been successfully
retrieved, the aggregator sends a response of the following format to the initial
requestor.

```javascript
{
  returnCode: int,
  error: string,
  documents: [
    {
      documentID: string,
      wordCount: int,
      pageLastIndexed: datetime,
      importantTokenRanges: [
        {
          fieldName: string,
          rangeStart: int,
          rangeEnd: int
        }
      ]
    }
  ],
  tokens: [
    token: string,
    ngramSize: int,
    documentOccurences: [
      {
        documentID: string,
        locations: [int]
      }
    ]
  ]
}
```

Valid return codes are:  

| return code | error | description |
|-------------|-------|-------------|
| 0 | success | Read completed without error. |
| 1 | throttling failure | Read failed due to throttling. |
| 2 | internal failure | Read failed due to internal error. |
| 3 | timeout failure | Read failed due to timeout. |

It is important to note that the role of the aggregator is performed
by the initial node that dispatched the search query.
