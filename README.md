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

## Concepts 

FileDepot concerns three entites: *Locker, Package, and Policy*, in which:

- Locker represents a reservation that the App requests for the user to upload files.
- Package is a set of files a user uploads to a specific Locker in FileDepot.
- Policy means the global or locker-specific policy, including expiration policy, access control policy, naming policy, file type policy, and so on.

## API
FileDepot provides a set of RESTful APTs.

### Login
- `POST /login`: Login interface for the client App. If successfully logged in, then the session token is stored in the cookie.
- `POST /logout`: Logout interface for the client App. Removes session token in the cookie.

### Locker
- `GET /locker`: Returns the IDs of all lockers owned by the requesting App.
- `POST /locker`: Reserves a locker under the name of the requesting App, and returns the locker ID.
        The payload of the POST request should specify the policies and initial states of this locker.
- `GET /locker/:id`: If the locker is owned by the requesting App, then returns the policies, states, and packages of the given locker.
- `PUT /locker/:id`: Changes the given locker's policies and states.
        The payload should specify **the delta** of the updated policies and states.
        Typical usages of this API include lock or unlock a locker, or postpone expiration date.
- `DELETE /locker/:id`: Deletes the given locker, and all packages of it.

### Package
- `GET /package`: Returns the IDs of all packages owned by the requesting App.
- `POST /package/locker/:locker_id`: If the locker belongs to the client App, then Creates a package in the specific locker, and returns the package ID. 
        The payload of this POST request should specify the policies and states of this locker.
- `POST /package/:id`: Upload a file to the specific package.
        The payload of the request is the file's content.
- `GET /package/:id`: If the package is in a locker owned by the requesting App, then returns the policies, states, and files in the given locker.
- `PUT /package/:id`: Changes the given package's policies and states.
        The payload should specify **the delta** of the updated policies and states.
        Typical usages of this API include lock or unlkock a package.
- `DELETE /package/:id`: Deletes the given package.

### Policy
TODO

## Policies
TODO

## Storage Backend
FileDepot can be driven by local storage or cloud storage. In this version we use Amazon S3.

The following describes the operations done in the storage backend when the APIs are called.

TODO