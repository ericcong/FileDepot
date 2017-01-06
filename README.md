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
id (UUID, 32-bytes)
uid (UUID, 32-bytes. The hashed user ID of the owner)
expires (Integer, timestamp. The timestamp that the locker expires)
policy:
  content_type (String, optional. acceptable MIME types)
  content_length_range (List of 2, optional. First element is min length, second is max length)
  expires_in_sec (Integer, required. The lifetime of the locker)
upload_info:
  url (String. The uploading link)
  fields (Dict. The uploading fields)
files (Dict. Information about the files in the locker): {
  $key (String. File's key in S3 ): {
    filename (String. File's name)
    size (Integer. Size in bytes)
    download_link (String. The presigned downloading link)
    download_link_expires (Integer, timestamp. The timestamp that the download link expires)
  }
]
```

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
  Supports query on expiration timestamp. Query format:
```
from: min expiration timestamp.
to: max expiration timestamp.
```

- `GET /lockers/:id`: Returns the Locker entity if exists.
If the locker doesn't exist, then return status code of 404.

- `POST /lockers`: Reserves a locker under the name of the requesting App, returns the Locker entity.
  Payload:
```
content_type: String, optional. The accepted type of the uploading files. Can be a MIME prefix like "image/".
content_length_range: List of 2 Integers, optional. A pair of (min_length, max_length).
expires_in_sec: Integer, optional, default as 3600. The number of seconds the Locker is valid for.
```

- `PUT /lockers/:id`: Extend the expiration time of the locker.
  Payload:
```
force: Boolean, default as False. If True, then always extends the expiration time. If False, then only extends if the locker is expired.
extension_in_sec: Integer, optional, default as 300. The extension time in seconds.
```
  Returns the updated LockerEntity. If the locker doesn't exist, then return status code of 404.

- `DELETE /lockers/:id`: Deletes the specified Locker, and all files in it.
  If the locker doesn't exist, then return status code of 404.

## Storage Backend
FileDepot is driven by Amazon AWS's S3 and DynamoDB.
The following describes the operations done in the storage backend when the APIs are called.
During the deployment, we should first specify a bucket in S3 for FileDepot to work on.
In the following discussion we will use this bucket as the root, denoted as `/`.
We also need a DynamoDB table, which records the states of Lockers, denoted as `db`.

- `POST /locker`:
  1. Generates a UUID denoted as `$uuid`, then creates the folder `/$uuid/`. Use `$uuid` as the Locker's ID.
  2. Creates the DynamoDB record for the Locker.
  3. Generates a presigned POST with S3's API for `/$uuid/`, with the conditions specified in the request.
  4. Constructs the Locker entity with the returning presigned uploading URL and fields information, and stores it in the DynamoDB record of this Locker.
  5. Returns the JSON representation of the Locker entity.

- `PUT /lockers/:id`:
  1. Retrieve the DynamoDB record of Locker #`id` from `db`.
  2. If `force == True`, then always extend expiration time; If `force == False`, then only extend when the locker expires. Compute the new expiration time by adding the current timestamp and the requested extension seconds.
  3. If the locker's expiration time is extended, then generate new presigned POST, otherwise not.
  4. Update and return the JSON representation of the Locker entity accordingly.

- `GET /lockers/:id`:
  1. Looks up this Locker in the DynamoDB.
  2. Constructs the JSON representation of the Locker entity according to the record.
  3. Check the files in `/$id/`, if any of them doesn't exist in the `files` dict, then create the presigned URL for it, and add it into the `files` dict.
  4. If any of the files' downloading link expires, then re-generate the presigned link, and update the Locker entity.
  5. If any of the element in `files` dict no longer exists in S3, then remove it.
  6. Returns the Locker entity.

- `DELETE /lockers/:id`:
  1. Deletes `/$id/`.
  2. Deletes the DynamoDB record of this Locker.

- `GET /lockers`: Just iterate all Lockers in the DynamoDB table that belong to the current user.
  If there's querystring, then set the query conditions accordingly.

## References
http://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.generate_presigned_post