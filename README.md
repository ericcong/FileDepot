# FileDepot
A general purpose uploading service based on "Locker Reservation" model.

## Locker Reservation Model
Locker Reservation Model can be explained with an analogy of Amazon Retuning Service.

When a customer wants to return a package back to Amazon, the workflow will be:

1. The customer tells Amazon that he wants to return a package.
2. Amazon sends a request to the Locker Service that is closest to the customer to reserve a locker.
3. The Locker Service reserves a locker, and tells Amazon the locker's ID.
4. Amazon binds the locker ID to the customer's return request, then tells the customer the reserved locker ID.
5. The customer puts the package into the reserved locker.
6. Amazon retrieves the package, and continues handling the corresponding return request.

FileDepot uses a similar model.
In FileDepot's use case:

- "The Locker Service" will be FileDepot.
- "Amazon" will be the App that uses FileDepot as its uploading service.
- "Customer" will be the user of this App.
- "Locker" represents a reservation that the App requests for the user to upload files.

## Locker Entity
A locker can be represented as such an entity:
```
id: UUID, 32-bytes
is_locked: Boolean, default as False
upload_url: String, optional
fields: Dict, optional
download_url: String, optional
```

If a Locker is not locked, then it accepts incoming uploads, but can't be downloaded, and its `upload_url` and `fields` fields are not null, but `download_url` is null.
Otherwise it doesn't accept uploads, but can be downloaded, and its `upload_url` and `fields` fields are null, but `download_url` is not null.

## API
FileDepot provides a set of RESTful APTs. The request and response are in the form of JSON strings.

### Login
- `POST /login`: Login interface for the client App. If successfully logged in, then the session token is stored in the cookie.

  Payload:
```
type: String, required. Type of login, such as "CAS", "OAuth"
cred: Dict. Cred information for login, different login types have different kinds of creds.
```

- `POST /logout`: Logout interface for the client App. Removes session token in the cookie.

  No Payload.

### Locker
- `GET /lockers`: Returns the IDs of all lockers owned by the requesting App.
  Format:
```
unlocked: List of unlocked locker IDs
locked: List of locked locker IDs
```

- `GET /lockers/:id`: Returns the Locker entity if exists.

  If the locker is not locked, then the returning Locker entity has the fields of `upload_url` and `fields`.

  If the locker is locked, then the returning Locker entity has the field of `download_url`.

  If the locker doesn't exist, then return status code of 404.

- `POST /lockers`: Reserves a locker under the name of the requesting App, returns the Locker entity.

  Payload:
```
content_type: String, optional. The accepted type of the uploading files. Can be a MIME prefix like "image/".
content_length_range: List of 2 Integers, optional. A pair of (min_length, max_length).
expires_in: Integer, optional. The number of seconds the Locker is valid for.
```

- `PUT /lockers/:id`: Locks the specified Locker, so that it won't receive new uploads.
  This also generates a presigned downloading URL, whose valid time is specified in the request:
```
valid_for: Integer, optional. The valid time in seconds.
```
  If there's no request payload, then `valid_for` is set to its default value of 300.
  Returns the updated LockerEntity, which includes `downloaded_url`.
  If the locker doesn't exist, then return status code of 404.

- `DELETE /lockers/:id`: Deletes the specified Locker, and all files in it.
  If the locker doesn't exist, then return status code of 404.

## Storage Backend
FileDepot is driven by Amazon AWS, specifically S3 and DynamoDB.
The following describes the operations done in the storage backend when the APIs are called.

During the deployment, we should first specify a bucket in S3 for FileDepot to work on.
In the following discussion we will use this bucket as the root, denoted as `/`.

Also during the deployment, there should be two folders created in this bucket, which contain locked and unlocked Lockers correspondingly.
Denote them as `/locked/`, and `/unlocked/`. 

We also need a DynamoDB table, which records the states of Lockers.

TODO: Atomic operations

- `POST /login`:
  1. Computes the hash of `(login_type, user_id)` denoted as `$uid`.
  2. Checks if both `/locked/$uid/` and `/unlocked/$uid/` exist. If any of them doesn't exist, then creates it.

- `POST /locker`:
  1. Generates a UUID denoted as `$uuid`, then creates the folder `/unlocked/$uid/$uuid/`. Use `$uuid` as the Locker's ID.
  2. Creates the DynamoDB record for the Locker.
  3. Generates a presigned POST with S3's API for `/unlocked/$uid/$uuid/`, with the conditions specified in the request.
  4. Constructs the Locker entity with the returning presigned uploading URL and fields information, and stores it in the DynamoDB record of this Locker.
  5. Returns the JSON representation of the Locker entity.

- `PUT /lockers/:id`:
  1. If `/unlocked/$uid/$id/` exists, then moves `/unlocked/$uid/$id/` to `/locked/$uid/$id/`.
  2. Updates the DynamoDB record of this Locker accordingly.
  3. Generates a presigned URL with S3's API for `/locked/$uid/$id/`, with the valid time specified in the request.
  4. Constructs the Locker entity with the returning presigned downloading URL, and save it in the DynamoDB record of this Locker.
  4. Returns the JSON representation of the Locker entity.

- `GET /lockers/:id`:
  1. Looks up this Locker in the DynamoDB.
  2. Constructs the JSON representation of the Locker entity according to the record.
  3. Returns the Locker entity.

- `DELETE /lockers/:id`:
  1. Deletes both `/unlocked/$uid/$id/` and `/locked/$uid/$id/`.
  2. Deletes the DynamoDB record of this Locker.

- `GET /lockers`: Just iterate all Lockers in the DynamoDB table that belong to the current App.

## References
http://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.generate_presigned_post