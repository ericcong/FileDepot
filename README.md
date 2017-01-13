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
expires (Integer, timestamp. The timestamp that the locker expires, i.e., all packages don't accept uploading.)
attributes (String, default to be null. Attributes of this locker, e.g. the purpose of this locker, or whether the locker is sealed or pending.)
packages: [
  {
    name (String. The name of this package)
    size (Integer. The size of this package)
    type (String, default to be null. MIME-type of this package)
    size_range (Pair, default to be null. Size range of this package)
    download_url (String, default to be null. The presigned downloading link)
    download_url_expires (Integer, timestamp, default to be null. The timestamp that the download link expires)
    upload_url (String. The presigned uploading link)
    upload_fields (Dict. The uploading fields)
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
- `GET /lockers`: Returns the IDs of all lockers owned by the requesting App which have the specified range of expiration timestamp, or specified attributes.
  Query format:
```
min_expires: Integer. Min expiration timestamp.
max_expires: Integer. Max expiration timestamp.
with_attributes: List of Strings. The attributes that the returning lockers should have.
without_attributes: List of Strings. The attributes that the returning lockers shouldn't have.
```

- `GET /lockers/:id`: Returns the Locker entity if exists.
If the locker doesn't exist, then return status code of 404.

- `POST /lockers`: Reserves a locker under the name of the requesting App, returns the Locker entity.
  Payload:
```
expires_in_sec (Integer, optional, default as 3600. The number of seconds the Locker is valid for)
attributes (String, optional. The attributes of this locker)
packages: (Ordered list. Packages that should be in this locker) [
  {
    name (String, optional. The name of this package; will use UUID if not specified)
    type (String, optional. MIME-type of this package)
    size_range (Pair, optional. Min and max acceptable size.)
  }
]
```

- `PUT /lockers/:id`: Extend the expiration time or the size of the locker, or change attributes.
  Payload:
```
extension_in_sec: Integer, optional, default as 300. The extension of expiration time in seconds.
attributes (String, optional. The attributes of this locker)
packages: (New packages that should be appended.) [
  {
    name (String, optional. The name of this package; will use UUID if not specified)
    type (String, optional. MIME-type of this package)
    size_range (Pair, optional. Min and max acceptable size.)
  }
]
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
The DynamoDB table should have two indices: `id-uid-index`, and `uid-index`.

- `POST /locker`:
  1. Generates a UUID denoted as `$uuid`, then creates the folder `/$uuid/`. Use `$uuid` as the Locker's ID.
  2. Creates the DynamoDB record for the Locker.
  3. Create package keys according to `package` list. Generate presigned POST for these keys, valid for `expires_in_sec` seconds.
  4. Constructs the Locker entity with the returning presigned uploading URLs and fields information, and stores it in the DynamoDB record of this Locker.
  5. Returns the JSON representation of the Locker entity.

- `PUT /lockers/:id`:
  1. Retrieve the DynamoDB record of Locker #`id` from `db`.
  2. If `extension_in_sec` is specified, then compute the new expiration time by adding the current timestamp and the requested extension seconds, and generate new presigned POST.
  3. If `packages` is specified, then create the new keys and corresponding presigned POST which expires along with the other existing presigned POSTs, and append to `packages` list of the locker entity.
  4. Update and return the JSON representation of the Locker entity accordingly.

- `GET /lockers/:id`:
  1. Looks up this Locker in the DynamoDB.
  2. Constructs the JSON representation of the Locker entity according to the record.
  3. Check the files in `/$id/`, if any of them doesn't have `download_url`, then create the presigned URL for it. 
  4. If any of the files' downloading link expires, then re-generate the presigned link.
  5. Update and return the Locker entity.

- `DELETE /lockers/:id`:
  1. Deletes `/$id/`.
  2. Deletes the DynamoDB record of this Locker.

- `GET /lockers`: Just iterate all Lockers in the DynamoDB table that belong to the current user.
  If there's querystring, then set the query conditions accordingly.

## References
http://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.generate_presigned_post